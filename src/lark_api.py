import os
import requests
from requests_toolbelt import MultipartEncoder
from dotenv import load_dotenv

load_dotenv()

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
    
    upload_file_response = upload_file(cv_file_path, parent_node, access_token)
    file_token = upload_file_response.get("data", {}).get("file_token")
    
    if not file_token:
        raise Exception("Failed to get file token after upload")

    data["File CV"] =  {
        "text": os.path.basename(cv_file_path),
        "link": f"https://filumxmp.sg.larksuite.com/file/{file_token}"
    }

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