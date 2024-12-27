import re
import json
import unicodedata
from colorama import Fore, Style

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