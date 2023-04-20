import json
import os
from dotenv import load_dotenv
import requests
from termcolor import cprint

load_dotenv()

INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
REPLY_ADMIN_ID = os.getenv("REPLY_ADMIN_ID")
TEST_MODE = os.getenv("TEST_MODE", False)


headers = {
    "accept": "application/json",
    "Intercom-Version": "2.8",
    "authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
}


async def api_request(url="https://api.intercom.io/articles"):
    response = requests.get(url, headers=headers)
    json_response = json.loads(response.text)
    return json_response


async def get_all_articles():
    articles = []
    url = "https://api.intercom.io/articles"
    while url:
        json_response = await api_request(url)
        articles += json_response["data"]
        url = json_response["pages"].get("next", None)
    return articles


async def get_conversation(conversation_id):
    url = f"https://api.intercom.io/conversations/{conversation_id}"
    return await api_request(url)


async def send_reply(conversation_id, message, message_type="comment"):
    url = f"https://api.intercom.io/conversations/{conversation_id}/reply"
    data = {
        "type": "admin",
        "admin_id": str(REPLY_ADMIN_ID),
        "message_type": message_type if not TEST_MODE else "note",
        "body": message,
    }
    cprint(f"Sending reply: {data}", "yellow")
    response = requests.post(
        url, headers=headers, json=data
    )  # returns the conversation
    cprint(f"Response: {response.text}", "magenta")
    json_response = json.loads(response.text)
    return json_response
