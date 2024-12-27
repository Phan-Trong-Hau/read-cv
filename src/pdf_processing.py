import re
import unicodedata
from PyPDF2 import PdfReader
from colorama import Fore, Style
from utils import clean_text

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