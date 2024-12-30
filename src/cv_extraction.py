import os
import re
import sys
import json
import google.generativeai as genai
from colorama import Fore, Style
from utils import clean_json_response
from dotenv import load_dotenv


exe_file = sys.executable
exe_parent = os.path.dirname(exe_file)
dotenv_path = os.path.join(exe_parent, ".env")

load_dotenv(dotenv_path=dotenv_path)

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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
            
            all_no_data = all(value == "NO DATA" for value in cv_info.values())
            if all_no_data:
                print(f"{Fore.YELLOW}Attempt {retry_count + 1}: All values are NO DATA, retrying...{Style.RESET_ALL}")
                retry_count += 1
                continue
            
            cv_info["Job Title"] = job_title
            return cv_info

        except Exception as e:
            print(f"{Fore.RED}Error extracting CV info (attempt {retry_count + 1}): {str(e)}{Style.RESET_ALL}")
            retry_count += 1

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