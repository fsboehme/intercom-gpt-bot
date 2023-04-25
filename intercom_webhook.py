import argparse
import asyncio
import hashlib
import hmac
import os
from bs4 import BeautifulSoup
from quart import Quart, request, jsonify
from dotenv import load_dotenv
from termcolor import cprint
from api.intercom import (
    close_conversation,
    get_conversation,
    send_reply,
    unassign_conversation,
)
from make_embeddings import make_embeddings

from reply import get_answer

load_dotenv()


REPLY_ADMIN_ID = os.getenv("REPLY_ADMIN_ID")
REPLY_ADMIN_NAME = os.getenv("REPLY_ADMIN_NAME")
AUTHOR_LABELS = {
    "user": "User",
    "lead": "Visitor",
    "admin": "Rep",
    "bot": "Bot",
}
EXPERIMENTAL_NOTICE_INNER = f"NOTE: {REPLY_ADMIN_NAME} is our experimental AI chatbot. It may not always provide a correct answer."
EXPERIMENTAL_NOTICE = (
    f"\n<div><hr><small><em>{EXPERIMENTAL_NOTICE_INNER}</em></small></div>"
)


app = Quart(__name__)


@app.route("/")
async def hello_world():
    app.add_background_task(process_webhook, "hello world")
    return "Hello World!"


@app.route("/webhook", methods=["POST"])
async def intercom_webhook():
    # Validate if the incoming request is from Intercom
    if not await validate_intercom_request(request):
        return jsonify(success=False, message="Invalid request"), 400

    # Process the webhook data asynchronously
    webhook_data = await request.json
    answer = app.add_background_task(process_webhook, webhook_data)
    return "OK"


async def process_webhook(webhook_data):
    # Add your async logic to process the webhook data here
    # e.g., store it in a database, trigger other actions, or make API calls
    print(f"Received webhook: {webhook_data}")

    item = webhook_data["data"]["item"]
    # print(f"Data > Item: {item}")
    if not item["type"] == "conversation":
        return
    if item["admin_assignee_id"] and item["admin_assignee_id"] != REPLY_ADMIN_ID:
        return

    conversation_id, messages = await prep_conversation(item)

    response_message = await get_answer("\n".join(messages))

    if "PASS" in response_message:
        # strip out PASS and send the rest of the message
        response_message = response_message.replace("PASS", "").strip()
        if response_message:
            await send_reply(conversation_id, response_message + EXPERIMENTAL_NOTICE)
        await unassign_conversation(conversation_id)
    elif "CLOSE" in response_message:
        # strip out CLOSE and send the rest of the message
        response_message = response_message.replace("CLOSE", "").strip()
        if response_message:
            await send_reply(conversation_id, response_message + EXPERIMENTAL_NOTICE)
        await send_reply(conversation_id, "CLOSE CONVERSATION")
        # await close_conversation(conversation_id)
    else:
        # cprint(response_message + EXPERIMENTAL_NOTICE, "red")
        await send_reply(conversation_id, response_message + EXPERIMENTAL_NOTICE)
    return response_message


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    # remove empty tags
    for tag in soup.find_all():
        if not tag.contents:
            tag.extract()

    # trim whitespace from start and end of the string
    return soup.get_text().strip()


async def prep_conversation(item):
    conversation_id = item["id"]
    user_name = AUTHOR_LABELS.get(item["source"]["author"]["type"])
    # skip first message if automated
    if item["source"]["delivered_as"] == "automated":
        messages = []
    else:
        msg = item["source"]["body"]
        messages = [f"{user_name}: {msg}"]

    if item["conversation_parts"]["total_count"] > 0:
        # make API request to fetch full conversation
        conversation = await get_conversation(conversation_id)
        # add conversation_parts to messages
        convo_parts = conversation["conversation_parts"]["conversation_parts"]
        # include only parts with body
        convo_parts = [part for part in convo_parts if part["body"]]

        if len(convo_parts) > 8:
            messages.append("...[messages truncated]...")

        for part in convo_parts[-8:]:
            # skip bot messages
            if part["author"]["type"] == "bot":
                continue
            # strip EXPERIMENTAL_NOTICE
            msg = part["body"].replace(EXPERIMENTAL_NOTICE, "")
            # strip EXPERIMENTAL_NOTICE_INNER (intercom sometimes modifies the HTML)
            msg = msg.replace(EXPERIMENTAL_NOTICE_INNER, "")
            msg = clean_html(msg)

            author_label = AUTHOR_LABELS.get(part["author"]["type"])
            messages.append(f"{author_label}: {msg}")

    return conversation_id, messages


async def validate_intercom_request(request):
    # Add your Intercom webhook secret here
    webhook_secret = os.getenv("INTERCOM_CLIENT_SECRET")

    # Get the computed signature from the header
    signature_header = request.headers.get("X-Hub-Signature")
    if not signature_header:
        return False

    # Get the request data
    request_data = await request.get_data()

    # Calculate the expected signature
    expected_signature = (
        "sha1="
        + hmac.new(
            webhook_secret.encode("utf-8"), request_data, hashlib.sha1
        ).hexdigest()
    )

    # Check if the signatures match
    return hmac.compare_digest(signature_header, expected_signature)


if __name__ == "__main__":
    # generate embeddings on startup
    asyncio.run(make_embeddings())
    app.run(port=5000)
