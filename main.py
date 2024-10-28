import os
import pandas as pd
from PyPDF2 import PdfReader
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
import unicodedata
import sys
from lark import post_data_to_lark_base

# Set console encoding to UTF-8
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

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
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        return clean_text(text)
    except Exception as e:
        print(f"Error reading PDF file {file_path}: {str(e)}")
        return None

def extract_cv_info(cv_text):
    if cv_text is None:
        return {
            "Full Name": "NO DATA",
            "Email": "NO DATA", 
            "Phone Number": "NO DATA",
            "Job Title": "NO DATA",
            "Date of Birth": "NO DATA",
            "Gender": "NO DATA",
            "Work Experience": "NO DATA",
            "Education": "NO DATA",
            "Note": "NO DATA"
        }

    model = genai.GenerativeModel('gemini-pro')
    prompt = (
        f"Please extract the following information from this CV and format as JSON. "
        f"For any field where data is not found, use 'NO DATA'. "
        f"Gender must be either 'Male' or 'Female'. "
        f"All values should be returned as plain strings, not as arrays or lists. "
        f"Please ensure the response is in valid JSON format. "
        f"The CV may contain Vietnamese text, please preserve Vietnamese characters. "
        f"Pay attention to the phone number and email to avoid confusion! "
        f"Please check the correct information fields! "
        f"Please extract: "
        f"- key: 'Full Name' "
        f"- key: 'Email' "
        f"- key: 'Phone Number' "
        f"- key: 'Job Title' "
        f"- key: 'Date of Birth' (format: DD/MM/YYYY) "
        f"- key: 'Gender' (only 'Male' or 'Female' or 'NO DATA') "
        f"- key: 'Work Experience' (with dates, companies, positions, and descriptions. Return as a single string, not an array) "
        f"- key: 'Education' (with dates, institutions, degree, and level. Return as a single string, not an array) "
        f"- key: 'Note' (include achievements, activities, and other data not related to the above fields. Return as a single string) "
        f"\nCV text: \n{cv_text}"
    )    
    try:
        response = model.generate_content(prompt)
        print(response.text)
        # Sử dụng hàm clean_json_response để làm sạch và phân tích cú pháp JSON
        cv_info = clean_json_response(response.text)
        if not cv_info:
            raise json.JSONDecodeError("No valid JSON found", "", 0)
    except Exception as e:
        print(f"Error extracting CV info: {str(e)}")
        # Nếu phân tích cú pháp thất bại, trả về các giá trị mặc định
        cv_info = {
            "Full Name": "NO DATA",
            "Email": "NO DATA",
            "Phone Number": "NO DATA", 
            "Job Title": "NO DATA",
            "Date of Birth": "NO DATA",
            "Gender": "NO DATA",
            "Work Experience": "NO DATA",
            "Education": "NO DATA",
            "Note": "NO DATA"
        }
    return cv_info

# def main():
#     input_folder = "./data"
#     output_folder = "./export"
#     os.makedirs(output_folder, exist_ok=True)
#     # Create a dataframe for all CVs
#     data = []

#     for filename in os.listdir(input_folder):
#         if filename.endswith(".pdf"):
#             try:
#                 file_path = os.path.join(input_folder, filename)
#                 cv_text = read_pdf(file_path)
#                 cv_info = extract_cv_info(cv_text)
#                 print(cv_info)

#                 # Convert all values to strings and handle encoding
#                 row_data = {
#                     "Name": clean_text(str(cv_info.get('Full Name', 'NO DATA'))),
#                     "Filename": str(filename),
#                     "Email": clean_text(str(cv_info.get('Email', 'NO DATA'))),
#                     "Phone": clean_text(str(cv_info.get('Phone Number', 'NO DATA'))),
#                     "Job Title": clean_text(str(cv_info.get('Job Title', 'NO DATA'))),
#                     "Date of Birth": clean_text(str(cv_info.get('Date of Birth', 'NO DATA'))),
#                     "Gender": clean_text(str(cv_info.get('Gender', 'NO DATA'))),
#                     "Work Experience": clean_text(str(cv_info.get('Work Experience', 'NO DATA'))),
#                     "Education": clean_text(str(cv_info.get('Education', 'NO DATA'))),
#                     "Note": clean_text(str(cv_info.get('Note', 'NO DATA')))
#                 }

#                 data.append(row_data)
#                 print(f"CV information for {filename} has been processed.")
#             except Exception as e:
#                 print(f"Error processing file {filename}: {str(e)}")
#                 continue

#     # Save to CSV using pandas with UTF-8 encoding
#     df = pd.DataFrame(data)
#     csv_path = os.path.join(output_folder, "summary_cv.csv")
#     df.to_csv(csv_path, index=False, encoding='utf-8')
#     print(f"Summary of CVs has been saved to {csv_path}")




def main():
    input_folder = "./data"
    
    # Get Lark Base configuration from environment variables
    base_id = os.getenv("BASE_ID_LARK")
    table_id = os.getenv("TABLE_ID_LARK")
    
    if not base_id or not table_id:
        raise Exception("BASE_ID_LARK and TABLE_ID_LARK environment variables are required")

    for filename in os.listdir(input_folder):
        if filename.endswith(".pdf"):
            try:
                file_path = os.path.join(input_folder, filename)
                cv_text = read_pdf(file_path)
                cv_info = extract_cv_info(cv_text)
                print(cv_info)

                # Prepare data for Lark Base
                lark_data = {
                    "Name": clean_text(str(cv_info.get('Full Name', 'NO DATA'))),
                    "Email": clean_text(str(cv_info.get('Email', 'NO DATA'))),
                    "Phone": clean_text(str(cv_info.get('Phone Number', 'NO DATA'))),
                    "Job Title": clean_text(str(cv_info.get('Job Title', 'NO DATA'))),
                    "Date of Birth": clean_text(str(cv_info.get('Date of Birth', 'NO DATA'))),
                    "Gender": clean_text(str(cv_info.get('Gender', 'NO DATA'))),
                    "Work Experience": clean_text(str(cv_info.get('Work Experience', 'NO DATA'))),
                    "Education": clean_text(str(cv_info.get('Education', 'NO DATA'))),
                    "Note": clean_text(str(cv_info.get('Note', 'NO DATA')))
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