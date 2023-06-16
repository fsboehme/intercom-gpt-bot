import json
import os
from dotenv import load_dotenv
import requests
from termcolor import cprint

load_dotenv()

INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
REPLY_ADMIN_ID = os.getenv("REPLY_ADMIN_ID")
HUMAN_ASSIGNEE_ID = os.getenv("HUMAN_ASSIGNEE_ID", None)
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
    cprint(message, "green")
    url = f"https://api.intercom.io/conversations/{conversation_id}/reply"
    payload = {
        "type": "admin",
        "admin_id": str(REPLY_ADMIN_ID),
        "message_type": message_type if not TEST_MODE else "note",
        "body": message,
    }
    response = requests.post(
        url, headers=headers, json=payload
    )  # returns the conversation
    json_response = json.loads(response.text)
    return json_response


async def manage_conversation(conversation_id, payload):
    url = f"https://api.intercom.io/conversations/{conversation_id}/parts"
    response = requests.post(url, headers=headers, json=payload)
    json_response = json.loads(response.text)
    return json_response


async def unassign_conversation(conversation_id):
    payload = {
        "message_type": "assignment",
        "admin_id": REPLY_ADMIN_ID,
        "assignee_id": "0",
    }
    return await manage_conversation(conversation_id, payload)


async def assign_conversation(conversation_id, assignee_id=REPLY_ADMIN_ID):
    payload = {
        "message_type": "assignment",
        "admin_id": REPLY_ADMIN_ID,
        "assignee_id": assignee_id,
    }
    return await manage_conversation(conversation_id, payload)


async def assign_conversation_to_human(conversation_id, assignee_id=HUMAN_ASSIGNEE_ID):
    # first unassign the conversation
    await unassign_conversation(conversation_id)
    # then assign it to the human
    payload = {
        "message_type": "assignment",
        "admin_id": REPLY_ADMIN_ID,
        "assignee_id": assignee_id,
    }
    conversation = await manage_conversation(conversation_id, payload)
    return (
        "conversation assigned to human"
        if int(assignee_id)
        in [
            conversation["team_assignee_id"],
            conversation["admin_assignee_id"],
        ]
        else "error assigning conversation to human"
    )


async def close_conversation(conversation_id):
    payload = {"message_type": "close", "admin_id": REPLY_ADMIN_ID}
    return await manage_conversation(conversation_id, payload)
