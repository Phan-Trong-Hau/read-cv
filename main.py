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


def post_data_to_lark_base(base_id, table_id, data):
    access_token = get_access_token()

    options_post_data = {
        "fields": data
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
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


# Load environment variables
load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


def clean_json_response(response_text):
    try:
        # Tìm phần JSON trong chuỗi phản hồi
        json_match = re.search(r'({[\s\S]*})', response_text)
        if json_match:
            json_str = json_match.group(1)
            # Thử chuyển đổi sang đối tượng JSON
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Nếu không thể phân tích cú pháp JSON, cố gắng làm sạch chuỗi
        print(f"Initial JSON parsing error: {str(e)}. Trying to clean up...")
        json_str = json_match.group(1)
        # Thay thế các dấu ngoặc kép không khớp bằng các dấu ngoặc kép hợp lệ
        json_str = re.sub(r'"|"', '"', json_str)
        json_str = re.sub(r"'|'", "'", json_str)
        # Thêm dấu phẩy sau các thuộc tính bị thiếu
        json_str = re.sub(r'"\s*:\s*"[^"]*"\s*(?=[^,}\s])', '",', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e2:
            print(f"Failed to clean and parse JSON: {str(e2)}")
    return None


def clean_text(text):
    if text:
        # Chuẩn hóa Unicode cho văn bản tiếng Việt
        text = unicodedata.normalize('NFKC', text)

        # Giữ lại các ký tự tiếng Việt và các ký tự ASCII cơ bản
        text = ''.join(c for c in text if unicodedata.category(c)[0] in ['L', 'N', 'P', 'Z'] or c in [' ', '-', '_', '@', '.'])

        # Loại bỏ các ký tự đặc biệt không in được
        text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]+', '', text)

        # Loại bỏ khoảng trắng thừa
        text = ' '.join(text.split())

        return text.strip()
    return text


def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf = PdfReader(file)
            text = ""
            for page in pdf.pages:
                # Extract text with layout preservation
                page_text = page.extract_text()
                if page_text:
                    # Add space between words that are stuck together
                    page_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', page_text)
                    # Add space between number and letter
                    page_text = re.sub(r'(\d)([A-Za-z])', r'\1 \2', page_text)
                    page_text = re.sub(r'([A-Za-z])(\d)', r'\1 \2', page_text)
                    # Add space between lines
                    page_text = re.sub(r'([^\n])\n([^\n])', r'\1\n\n\2', page_text)
                    # Add extra newline between sections
                    page_text = re.sub(r'([.!?])\s*(\w)', r'\1\n\n\2', page_text)
                    # Add extra newline between bullet points
                    page_text = re.sub(r'(•|\*|\-|\d+\.)\s*', r'\n\1 ', page_text)
                    # Add extra newline between pages to prevent text merging
                    text += page_text + "\n\n\n"
            
            # Clean up excessive whitespace while preserving important spacing
            text = re.sub(r'\n{5,}', '\n\n\n\n', text)  # Reduce multiple newlines but keep quadruple newlines
            text = re.sub(r' {2,}', ' ', text)  # Reduce multiple spaces
            
            return clean_text(text)
    except Exception as e:
        print(f"Error reading PDF file {file_path}: {str(e)}")
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
        f"2. Email - This must be a valid email address format that does not contain phone numbers"
        f"3. Phone Number - This must be a valid phone number format and cannot be part of the email address"
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
            print(response.text)
            cv_info = clean_json_response(response.text)
            
            if not cv_info:
                raise json.JSONDecodeError("No valid JSON found", "", 0)
            
            # Check if all values are "NO DATA"
            all_no_data = all(value == "NO DATA" for value in cv_info.values())
            if all_no_data:
                print(f"Attempt {retry_count + 1}: All values are NO DATA, retrying...")
                retry_count += 1
                continue
            
            # Add job title to CV info
            cv_info["Job Title"] = job_title
            return cv_info

        except Exception as e:
            print(f"Error extracting CV info (attempt {retry_count + 1}): {str(e)}")
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
    input_folder = "./data"
    
    # Get Lark Base configuration from environment variables
    base_id = os.getenv("BASE_ID_LARK")
    table_id = os.getenv("TABLE_ID_LARK")
    
    if not base_id or not table_id:
        raise Exception("BASE_ID_LARK and TABLE_ID_LARK environment variables are required")

    # Get job title from user input once
    # job_title = input("Please enter the job title for all CVs: ")
    job_title = "Software Engineer"

    for filename in os.listdir(input_folder):
        if filename.endswith(".pdf"):
            try:
                file_path = os.path.join(input_folder, filename)
                cv_text = read_pdf(file_path)
                cv_info = extract_cv_info(cv_text, job_title)
                print(cv_text)

                # Prepare data for Lark Base
                lark_data = {
                    "Name": clean_text(str(cv_info.get('Full Name', 'ERROR: Missing data'))),
                    "Email": clean_text(str(cv_info.get('Email', 'ERROR: Missing data'))),
                    "Phone": clean_text(str(cv_info.get('Phone Number', 'ERROR: Missing data'))),
                    "Job Title": clean_text(str(cv_info.get('Job Title', 'ERROR: Missing data'))),
                    "Date of Birth": clean_text(str(cv_info.get('Date of Birth', 'ERROR: Missing data'))),
                    "Gender": clean_text(str(cv_info.get('Gender', 'ERROR: Missing data'))),
                    "Work Experience": clean_text(str(cv_info.get('Work Experience', 'ERROR: Missing data'))),
                    "Education": clean_text(str(cv_info.get('Education', 'ERROR: Missing data'))),
                    "Note": clean_text(str(cv_info.get('Note', 'ERROR: Missing data')))
                }

                # Send data to Lark Base
                response = post_data_to_lark_base(base_id, table_id, lark_data)
                print(f"CV information for {filename} has been sent to Lark Base.")
            except Exception as e:
                print(f"Error processing file {filename}: {str(e)}")
                continue

    print("All CV data has been sent to Lark Base")


if __name__ == "__main__":
    main()