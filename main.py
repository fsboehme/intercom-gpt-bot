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
from management.clean_chroma_sections import clean_chroma_sections
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
UPDATE_ARTICLES_SECRET = os.getenv("UPDATE_ARTICLES_SECRET")


app = Quart(__name__)


@app.route("/")
async def hello_world():
    # if update articles secret in GET request is correct, update embeddings
    if request.args.get("update_articles") == UPDATE_ARTICLES_SECRET:
        # restart server
        subprocess.Popen(["/home/flask/deploy.sh"])
        return "Articles updated!"
    return "Beep boop! We're live!"


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
    print(f"Received webhook: {webhook_data}")

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

    # fetch conversation again from api to make sure it hasn't been updated
    conversation = await get_conversation(item["id"])
    # check conversation parts to see if a new reply has been added (ignoring bot replies)
    fetched_non_bot_conversation_parts = [
        cp
        for cp in conversation["conversation_parts"]["conversation_parts"]
        if cp["author"]["type"] != "bot"
    ]
    # if webhook item has no conversation parts, any non-bot message will be newer
    # otherwise, we check if the last message is the same (id) as the last non-bot message
    webhook_item_conversation_parts = item["conversation_parts"]["conversation_parts"]
    if fetched_non_bot_conversation_parts and (
        not webhook_item_conversation_parts
        or fetched_non_bot_conversation_parts[-1]["id"]
        != webhook_item_conversation_parts[-1]["id"]
    ):
        # there's already a newer reply, don't reply
        cprint("Conversation already updated", "red")
        return

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
        result = await unassign_conversation(conversation_id)
    elif "CLOSE" in response_message:
        # strip out CLOSE and send the rest of the message
        response_message = response_message.replace("CLOSE", "").strip()
        if response_message:
            response_message = clean_html(response_message)
            result = await send_reply(
                conversation_id, response_message + EXPERIMENTAL_NOTICE
            )
        if TEST_MODE:
            result = await send_reply(conversation_id, "CLOSE CONVERSATION", "note")
        else:
            result = await close_conversation(conversation_id)
    else:
        response_message = clean_html(response_message)
        result = await send_reply(
            conversation_id, response_message + EXPERIMENTAL_NOTICE
        )
    return result


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    block_elements = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]
    inline_elements = ["a", "em", "strong", "span", "b", "i", "code"]

    def wrap_text_and_inline_in_p(tag):
        current_paragraph = None
        for content in list(tag.contents):
            if (isinstance(content, NavigableString) and content.string.strip()) or (
                content.name in inline_elements
            ):
                if current_paragraph is None:
                    current_paragraph = soup.new_tag("p")
                    content.insert_before(current_paragraph)
                current_paragraph.append(content)
            else:
                current_paragraph = None

    wrap_text_and_inline_in_p(soup)

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
async def deploy():
    signature = request.headers.get("X-Hub-Signature-256")
    if signature is None:
        return "Forbidden", 403

    payload = await request.get_data()

    key = GITHUB_WEBHOOK_SECRET.encode("utf-8")
    digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
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
