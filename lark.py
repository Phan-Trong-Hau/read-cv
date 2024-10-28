import os
import requests

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
