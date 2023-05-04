import asyncio
import hashlib
import hmac
import os
import subprocess
from bs4 import BeautifulSoup, NavigableString
from quart import Quart, request, jsonify
from dotenv import load_dotenv
from termcolor import cprint
from api.intercom import (
    close_conversation,
    get_conversation,
    send_reply,
    unassign_conversation,
)
from clean_chroma_sections import clean_chroma_sections
from make_embeddings import make_embeddings

from reply import get_answer

load_dotenv()


REPLY_ADMIN_ID = int(os.getenv("REPLY_ADMIN_ID"))
REPLY_ADMIN_NAME = os.getenv("REPLY_ADMIN_NAME")
AUTHOR_LABELS = {
    "user": "User",
    "lead": "User",
    "admin": "Rep",
    "bot": "Bot",
}
EXPERIMENTAL_NOTICE_INNER = f"NOTE: {REPLY_ADMIN_NAME} is our experimental AI chatbot. It may not always provide a correct answer. A human will follow up if needed."
DIVIDER = "<p>_____</p>"
EXPERIMENTAL_NOTICE = f"{DIVIDER}<p><i>{EXPERIMENTAL_NOTICE_INNER}</i></p>"
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


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
    result = app.add_background_task(process_webhook, webhook_data)
    return "OK"


async def process_webhook(webhook_data):
    # Add your async logic to process the webhook data here
    # e.g., store it in a database, trigger other actions, or make API calls
    print(f"Received webhook: {webhook_data}")
    if webhook_data == "hello world":
        return

    item = webhook_data["data"]["item"]
    # print(f"Data > Item: {item}")
    if not item["type"] == "conversation":
        return
    # only reply to conversations that are unassigned or assigned to the bot
    if item["admin_assignee_id"] and item["admin_assignee_id"] != REPLY_ADMIN_ID:
        if TEST_MODE:
            # in test mode, we want to process all conversations
            cprint(
                f"Conversation already assigned to {item['admin_assignee_id']}", "red"
            )
        else:
            return

    chat_history = await prep_conversation(item)

    response_message = await get_answer("\n".join(chat_history))

    result = await send_response(item, response_message)
    return result


async def send_response(conversation, response_message):
    conversation_id = conversation["id"]
    if "PASS" in response_message:
        # strip out PASS and send the rest of the message
        response_message = response_message.replace("PASS", "").strip()
        response_message = clean_html(response_message)
        if response_message:
            result = await send_reply(
                conversation_id, response_message + EXPERIMENTAL_NOTICE
            )
        # if assigned to REPLY_ADMIN_ID
        elif conversation["admin_assignee_id"] == REPLY_ADMIN_ID:
            result = await send_reply(
                conversation_id,
                "Sorry, I don't know how to answer that. You can try rephrasing your question. Otherwise, I will leave this question for a human to answer.",
            )
        result = await unassign_conversation(conversation_id)
    elif "CLOSE" in response_message:
        # strip out CLOSE and send the rest of the message
        response_message = response_message.replace("CLOSE", "").strip()
        if response_message:
            response_message = clean_html(response_message)
            result = await send_reply(
                conversation_id, response_message + EXPERIMENTAL_NOTICE
            )
        result = await send_reply(conversation_id, "CLOSE CONVERSATION", "note")
        # await close_conversation(conversation_id)
    else:
        response_message = clean_html(response_message)
        result = await send_reply(
            conversation_id, response_message + EXPERIMENTAL_NOTICE
        )
    return result


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    block_elements = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]
    inline_elements = ["a", "em", "strong", "span"]

    # wrap any standalone plain text in a <p> tag
    def wrap_text_in_p(tag):
        for text in tag.find_all(string=True):
            if (
                isinstance(text, NavigableString)
                and text.parent.name not in block_elements + inline_elements
            ):
                text.wrap(soup.new_tag("p"))

    wrap_text_in_p(soup)

    # check if the tag has any visible content
    def has_visible_content(tag):
        if any(
            child.string.strip()
            for child in tag.contents
            if hasattr(child, "string")
            and child.string is not None
            and child.string.strip()
        ):
            return True
        if tag.find_all(["img", "a", "em"]):
            return True
        return False

    # remove only those tags that have no visible content
    for tag in soup.find_all():
        if (
            (tag.name not in ["img", "br"])
            and (not has_visible_content(tag))
            and (not tag.string)
        ):
            tag.extract()
        elif isinstance(tag.string, str):
            tag.string = tag.string.strip()

    # convert the soup object back to HTML
    cleaned_html = str(soup)
    return cleaned_html


async def prep_conversation(item):
    user_name = AUTHOR_LABELS.get(item["source"]["author"]["type"])
    # skip first message if automated
    if item["source"]["delivered_as"] == "automated":
        messages = []
    else:
        msg = item["source"]["body"]
        messages = [f"{user_name}: {msg}"]

    if item["conversation_parts"]["total_count"] > 0:
        # make API request to fetch full conversation
        conversation = await get_conversation(item["id"])
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
            # skip if note and from REPLY_ADMIN_ID
            if part["part_type"] == "note" and part["author"]["id"] == REPLY_ADMIN_ID:
                continue
            # strip EXPERIMENTAL_NOTICE
            msg = part["body"].replace(EXPERIMENTAL_NOTICE, "")
            # strip DIVIDER and EXPERIMENTAL_NOTICE_INNER (intercom sometimes modifies the HTML)
            msg = msg.replace(DIVIDER, "")
            msg = msg.replace(EXPERIMENTAL_NOTICE_INNER, "")
            msg = clean_html(msg)

            author_label = AUTHOR_LABELS.get(part["author"]["type"])
            messages.append(f"{author_label}: {msg}")

    return messages


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


@app.route("/deploy", methods=["POST"])
def deploy():
    signature = request.headers.get("X-Hub-Signature-256")
    if signature is None:
        return "Forbidden", 403

    payload = request.get_data()
    digest = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={digest}"

    if not hmac.compare_digest(expected_signature, signature):
        return "Forbidden", 403

    if request.method == "POST":
        subprocess.Popen(["/home/flask/deploy.sh"])
        return "OK", 200
    else:
        return "Method Not Allowed", 405


if __name__ == "__main__":
    # generate embeddings on startup
    asyncio.run(make_embeddings())
    clean_chroma_sections()
    app.run(port=5000)
