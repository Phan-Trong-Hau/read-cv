import os
import sys
from colorama import init, Fore, Style
from dotenv import load_dotenv
from lark_api import get_records_from_lark, post_data_to_lark_base
from pdf_processing import read_pdf
from cv_extraction import extract_cv_info
from utils import clean_text

extDataDir = os.getcwd()
if getattr(sys, 'frozen', False):
    extDataDir = sys._MEIPASS
load_dotenv(dotenv_path=os.path.join(extDataDir, '.env'))

init()

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    base_folder = os.path.join(base_path, "..", "data")
    default_job_title = "Không nằm trong thư mục nào"

    base_id = os.getenv("BASE_ID_LARK")
    table_id = os.getenv("TABLE_ID_LARK")

    print(f"Base ID: {base_id}")

    if not base_id or not table_id:
        raise Exception("BASE_ID_LARK and TABLE_ID_LARK environment variables are required")

    existing_records = get_records_from_lark(base_id, table_id)
    existing_files = set()
    if existing_records.get("data", {}).get("items"):
        for record in existing_records["data"]["items"]:
            if record.get("fields", {}).get("File CV"):
                existing_files.add(record["fields"]["File CV"]["text"])

    for root, dirs, files in os.walk(base_folder):
        for filename in files:
            if filename.endswith(".pdf"):
                if filename in existing_files:
                    print(f"{Fore.YELLOW}Skipping {filename} as it already exists in Lark Base{Style.RESET_ALL}")
                    continue

                try:
                    file_path = os.path.join(root, filename)
                    cv_text = read_pdf(file_path)

                    # Extract job title and source from directory structure
                    relative_path = os.path.relpath(root, base_folder)
                    path_parts = relative_path.split(os.sep)
                    if len(path_parts) >= 2:
                        job_title = path_parts[0]
                        source = path_parts[1]
                    else:
                        job_title = default_job_title
                        source = "Unknown"

                    cv_info = extract_cv_info(cv_text, job_title)

                    lark_data = {
                        "Name": clean_text(str(cv_info.get('Full Name', 'ERROR: Missing data'))),
                        "Email": {"text": clean_text(str(cv_info.get('Email', 'ERROR: Missing data'))), "link": f"mailto:{clean_text(str(cv_info.get('Email', 'ERROR: Missing data')))}"},
                        "Phone": clean_text(str(cv_info.get('Phone Number', 'ERROR: Missing data'))),
                        "Position Applied (Tool)": clean_text(str(job_title)),
                        "Source": clean_text(str(source)),
                        "Ngày sinh (Tool)": clean_text(str(cv_info.get('Date of Birth', 'ERROR: Missing data'))),
                        "Giới tính (Tool)": clean_text(str(cv_info.get('Gender', 'ERROR: Missing data'))),
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