import os
import pandas as pd
from PyPDF2 import PdfReader
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
import unicodedata
import sys
import requests
from requests_toolbelt import MultipartEncoder
from colorama import init, Fore, Style

exe_file = sys.executable
exe_parent = os.path.dirname(exe_file)
dotenv_path = os.path.join(exe_parent, ".env")

load_dotenv(dotenv_path=dotenv_path)
# Initialize colorama
init()

# Set console encoding to UTF-8
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')


def get_url_record_lark_base(base_id, table_id):
    return f"https://open.larksuite.com/open-apis/bitable/v1/apps/{base_id}/tables/{table_id}/records"


def get_access_token():
    app_id = os.getenv("APP_ID_LARK_BASE")
    app_secret = os.getenv("APP_SECRET_LARK_BASE")

    options_get_token = {
        "app_id": app_id,
        "app_secret": app_secret,
    }

    response = requests.post(
        "https://open.larksuite.com/open-apis/auth/v3/app_access_token/internal",
        json=options_get_token,
        headers={"Content-Type": "application/json"}
    )

    token = response.json()

    if not token.get("app_access_token"):
        raise Exception("Error getting access token from Lark Base.")
    
    return token["app_access_token"]


def upload_file(file_path, parent_node, access_token):
    file_size = os.path.getsize(file_path)
    url = "https://open.larksuite.com/open-apis/drive/v1/files/upload_all"
    
    form = {'file_name': os.path.basename(file_path),
            'parent_type': 'explorer',
            'parent_node': parent_node,
            'size': str(file_size),
            'file': (open(file_path, 'rb'))}  
    multi_form = MultipartEncoder(form)
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    headers['Content-Type'] = multi_form.content_type
    response = requests.request("POST", url, headers=headers, data=multi_form)
    return response.json()


def get_records_from_lark(base_id, table_id):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(
        get_url_record_lark_base(base_id, table_id),
        headers=headers
    )
    
    return response.json()


def post_data_to_lark_base(base_id, table_id, data, cv_file_path):
    access_token = get_access_token()
    parent_node = os.getenv("PARENT_NODE_LARK")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    # Upload file to Lark Drive
    upload_file_response = upload_file(cv_file_path, parent_node, access_token)

    # Get file token from upload response
    file_token = upload_file_response.get("data", {}).get("file_token")
    
    if not file_token:
        raise Exception("Failed to get file token after upload")

    data["File CV"] =  {
        "text": os.path.basename(cv_file_path),
        "link": f"https://filumxmp.sg.larksuite.com/file/{file_token}"
    }

    # Post record to Lark Bitable with file reference
    options_post_data = {
        "fields": data
    }

    response = requests.post(
        get_url_record_lark_base(base_id, table_id),
        json=options_post_data,
        headers=headers
    )

    res = response.json()
    if res.get("msg") != "success":
        raise Exception(f"Error when sending data to Lark: {res}")

    return res

# Configure the Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


def clean_json_response(response_text):
    try:
        json_match = re.search(r'({[\s\S]*})', response_text)
        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}Initial JSON parsing error: {str(e)}. Trying to clean up...{Style.RESET_ALL}")
        json_str = json_match.group(1)
        json_str = re.sub(r'"|"', '"', json_str)
        json_str = re.sub(r"'|'", "'", json_str)
        json_str = re.sub(r'"\s*:\s*"[^"]*"\s*(?=[^,}\s])', '",', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e2:
            print(f"{Fore.RED}Failed to clean and parse JSON: {str(e2)}{Style.RESET_ALL}")
    return None


def clean_text(text):
    if text:
        text = unicodedata.normalize('NFKC', text)
        text = ''.join(c for c in text if unicodedata.category(c)[0] in ['L', 'N', 'P', 'Z'] or c in [' ', '-', '_', '@', '.'])
        text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]+', '', text)
        text = ' '.join(text.split())

        return text.strip()
    return text


def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf = PdfReader(file)
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    page_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', page_text)
                    page_text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', page_text)
                    page_text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', page_text)
                    page_text = re.sub(r'([^\n])\n([^\n])', r'\1\n\n\2', page_text)
                    page_text = re.sub(r'([.!?])\s*(\w)', r'\1\n\n\2', page_text)
                    page_text = re.sub(r'(•|\*|\-|\d+\.)\s*', r'\n\1 ', page_text)
                    text += page_text + "\n\n\n"
            
            text = re.sub(r'\n{5,}', '\n\n\n\n', text) 
            text = re.sub(r' {2,}', ' ', text)  
            
            return clean_text(text)
    except Exception as e:
        print(f"{Fore.RED}Error reading PDF file {file_path}: {str(e)}{Style.RESET_ALL}")
        return None


def extract_cv_info(cv_text, job_title):
    if cv_text is None:
        return {
            "Full Name": "ERROR: No CV text provided",
            "Email": "ERROR: No CV text provided", 
            "Phone Number": "ERROR: No CV text provided",
            "Job Title": job_title,
            "Date of Birth": "ERROR: No CV text provided",
            "Gender": "ERROR: No CV text provided",
            "Work Experience": "ERROR: No CV text provided",
            "Education": "ERROR: No CV text provided",
            "Note": "ERROR: No CV text provided"
        }

    model = genai.GenerativeModel('gemini-pro')
    prompt = (
        f"Please carefully extract the following CRITICAL information from this CV and format as JSON. "
        f"These 3 fields are the most important - please verify them multiple times:"
        f"1. Full Name - This must be the candidate's complete name"
        f"2. Email - This must be a valid email address format. IMPORTANT: Check that the email does not contain "
        f"any phone numbers before or within it, If an email starts with 9-12 consecutive numbers, it is a phone number, not an email (e.g., '0123456789email@domain.com' is invalid). "
        f"The email should only contain letters, numbers, dots, and @ symbol in standard email format."
        f"3. Phone Number - This must be a valid phone number format. Ensure this is completely separate from the email address"
        f"\nFor any field where data is not found, use 'NO DATA'. "
        f"Gender must be either 'Male' or 'Female'. "
        f"All values should be returned as plain strings, not as arrays or lists. "
        f"Please ensure the response is in valid JSON format. "
        f"The CV may contain Vietnamese text, please preserve Vietnamese characters. "
        f"Please extract: "
        f"- key: 'Full Name' (CRITICAL - verify carefully)"
        f"- key: 'Email' (CRITICAL - verify carefully, must not contain phone number)"
        f"- key: 'Phone Number' (CRITICAL - verify carefully, must not be part of email)"
        f"- key: 'Date of Birth' (format: DD/MM/YYYY) "
        f"- key: 'Gender' (only 'Male' or 'Female' or 'NO DATA') "
        f"- key: 'Work Experience' (with dates, companies, positions, and descriptions. Return as a single string, not an array) "
        f"- key: 'Education' (with dates, institutions, degree, and level. Return as a single string, not an array) "
        f"- key: 'Note' (include achievements, activities, and other data not related to the above fields. Return as a single string) "
        f"\nCV text: \n{cv_text}"
    )    

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = model.generate_content(prompt)
            cv_info = clean_json_response(response.text)
            
            if cv_info and cv_info.get('Email') != 'NO DATA':
                email = cv_info['Email']
                if re.search(r'\d{9,}', email):
                    print(f"{Fore.RED}Warning: Possible phone number found in email: {email}{Style.RESET_ALL}")


            if not cv_info:
                raise json.JSONDecodeError("No valid JSON found", "", 0)
            
            # Check if all values are "NO DATA"
            all_no_data = all(value == "NO DATA" for value in cv_info.values())
            if all_no_data:
                print(f"{Fore.YELLOW}Attempt {retry_count + 1}: All values are NO DATA, retrying...{Style.RESET_ALL}")
                retry_count += 1
                continue
            
            # Add job title to CV info
            cv_info["Job Title"] = job_title
            return cv_info

        except Exception as e:
            print(f"{Fore.RED}Error extracting CV info (attempt {retry_count + 1}): {str(e)}{Style.RESET_ALL}")
            retry_count += 1

    # If all retries failed, return error values
    return {
        "Full Name": "ERROR: Failed to extract data",
        "Email": "ERROR: Failed to extract data",
        "Phone Number": "ERROR: Failed to extract data", 
        "Job Title": job_title,
        "Date of Birth": "ERROR: Failed to extract data",
        "Gender": "ERROR: Failed to extract data",
        "Work Experience": "ERROR: Failed to extract data",
        "Education": "ERROR: Failed to extract data",
        "Note": "ERROR: Failed to extract data"
    }

def main():
    # Get the absolute path of the executable or script
    if getattr(sys, 'frozen', False):
        # If running as compiled executable
        base_path = os.path.dirname(sys.executable)
    else:
        # If running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    base_folder = os.path.join(base_path, "data")
    default_job_title = "Không nằm trong thư mục nào"
    
    # Get Lark Base configuration from environment variables
    base_id = os.getenv("BASE_ID_LARK")
    table_id = os.getenv("TABLE_ID_LARK")
    
    if not base_id or not table_id:
        raise Exception("BASE_ID_LARK and TABLE_ID_LARK environment variables are required")

    # Get existing records from Lark Base
    existing_records = get_records_from_lark(base_id, table_id)
    existing_files = set()
    if existing_records.get("data", {}).get("items"):
        for record in existing_records["data"]["items"]:
            if record.get("fields", {}).get("File CV"):
                existing_files.add(record["fields"]["File CV"]["text"])

    # First process PDFs in root data folder
    for filename in os.listdir(base_folder):
        if filename.endswith(".pdf"):
            if filename in existing_files:
                print(f"{Fore.YELLOW}Skipping {filename} as it already exists in Lark Base{Style.RESET_ALL}")
                continue
                
            try:
                file_path = os.path.join(base_folder, filename)
                cv_text = read_pdf(file_path)
                cv_info = extract_cv_info(cv_text, default_job_title)

                # Prepare data for Lark Base
                lark_data = {
                    "Name": clean_text(str(cv_info.get('Full Name', 'ERROR: Missing data'))),
                    "Email": {"text": clean_text(str(cv_info.get('Email', 'ERROR: Missing data'))), "link": f"mailto:{clean_text(str(cv_info.get('Email', 'ERROR: Missing data')))}"},
                    "Phone": clean_text(str(cv_info.get('Phone Number', 'ERROR: Missing data'))),
                    "Position Applied": clean_text(str(default_job_title)),
                    "Ngày sinh": clean_text(str(cv_info.get('Date of Birth', 'ERROR: Missing data'))),
                    "Giới tính": clean_text(str(cv_info.get('Gender', 'ERROR: Missing data'))),
                    "Working Experience": clean_text(str(cv_info.get('Work Experience', 'ERROR: Missing data'))),
                    "Education": clean_text(str(cv_info.get('Education', 'ERROR: Missing data'))),
                    "Note": clean_text(str(cv_info.get('Note', 'ERROR: Missing data')))
                }

                response = post_data_to_lark_base(base_id, table_id, lark_data, file_path)
                print(f"{Fore.GREEN}CV information for {filename} has been sent to Lark Base.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error processing file {filename}: {str(e)}{Style.RESET_ALL}")
                continue

    # Then process subdirectories
    for item in os.listdir(base_folder):
        item_path = os.path.join(base_folder, item)
        if os.path.isdir(item_path):
            job_title = item
            print(f"Processing CVs for position: {job_title}")
            
            for filename in os.listdir(item_path):
                if filename.endswith(".pdf"):
                    if filename in existing_files:
                        print(f"{Fore.YELLOW}Skipping {filename} as it already exists in Lark Base{Style.RESET_ALL}")
                        continue
                        
                    try:
                        file_path = os.path.join(item_path, filename)
                        cv_text = read_pdf(file_path)
                        cv_info = extract_cv_info(cv_text, job_title)

                        lark_data = {
                            "Name": clean_text(str(cv_info.get('Full Name', 'ERROR: Missing data'))),
                            "Email": {"text": clean_text(str(cv_info.get('Email', 'ERROR: Missing data'))), "link": f"mailto:{clean_text(str(cv_info.get('Email', 'ERROR: Missing data')))}"},
                            "Phone": clean_text(str(cv_info.get('Phone Number', 'ERROR: Missing data'))),
                            "Position Applied": clean_text(str(job_title)),
                            "Ngày sinh": clean_text(str(cv_info.get('Date of Birth', 'ERROR: Missing data'))),
                            "Giới tính": clean_text(str(cv_info.get('Gender', 'ERROR: Missing data'))),
                            "Working Experience": clean_text(str(cv_info.get('Work Experience', 'ERROR: Missing data'))),
                            "Education": clean_text(str(cv_info.get('Education', 'ERROR: Missing data'))),
                            "Note": clean_text(str(cv_info.get('Note', 'ERROR: Missing data')))
                        }

                        response = post_data_to_lark_base(base_id, table_id, lark_data, file_path)
                        print(f"{Fore.GREEN}CV information for {filename} has been sent to Lark Base.{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Error processing file {filename}: {str(e)}{Style.RESET_ALL}")
                        continue

    print(f"{Fore.GREEN}All CV data has been sent to Lark Base{Style.RESET_ALL}")


if __name__ == "__main__":
    main()