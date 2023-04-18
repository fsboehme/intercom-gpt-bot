import json
import os
from dotenv import load_dotenv
import requests

load_dotenv()

INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")


headers = {
    "accept": "application/json",
    "Intercom-Version": "2.8",
    "authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
}


def api_request(url="https://api.intercom.io/articles"):
    response = requests.get(url, headers=headers)
    json_response = json.loads(response.text)
    return json_response


# walk through the pages
def get_all_articles():
    articles = []
    url = "https://api.intercom.io/articles"
    while url:
        json_response = api_request(url)
        articles += json_response["data"]
        url = json_response["pages"].get("next", None)
    return articles


def get_conversation(conversation_id):
    url = f"https://api.intercom.io/conversations/{conversation_id}"
    return api_request(url)
