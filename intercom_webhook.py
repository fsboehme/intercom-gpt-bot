import asyncio
import hashlib
import hmac
import os
import time
from quart import Quart, request, jsonify
from dotenv import load_dotenv
from api_intercom import get_conversation

from reply import get_answer

load_dotenv()


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
    print("Webhook processing asynchronously")
    return "OK"


async def process_webhook(webhook_data):
    # Add your async logic to process the webhook data here
    # e.g., store it in a database, trigger other actions, or make API calls
    print(f"Received webhook: {webhook_data}")
    if webhook_data == "hello world":
        print("hello")
        await asyncio.sleep(5)
        print("world")
        return
    item = webhook_data["data"]["item"]
    # print(f"Data > Item: {item}")
    if not item["type"] == "conversation":
        return

    conversation_id = item["id"]

    # user_name = item["conversation_message"]["author"].get("name", "User")
    user_name = item["conversation_message"]["author"].get("type", "User")
    msg = item["conversation_message"]["body"]
    # messages = [{"role": "user", "content": f"{author_name}: {msg}"}]
    messages = [f"{user_name}: {msg}"]
    if item["conversation_parts"]["total_count"] > 0:
        # make API request to fetch full conversation
        conversation = await get_conversation(conversation_id)
        # add conversation_parts to messages
        convo_parts = conversation["conversation_parts"]["conversation_parts"]
        if len(convo_parts) > 10:
            messages.append("...[messages truncated]...")
        for part in convo_parts[-10:]:
            # skip if body is empty
            if not part["body"]:
                continue

            # todo: add logic to handle 'assistant' replies from GPT
            # author_name = part["author"].get("name", user_name)
            author_name = part["author"]["type"]
            msg = part["body"]
            # messages.append({"role": "user", "content": f"{author_name}: {msg}"})
            messages.append(f"{author_name}: {msg}")
    answer = await get_answer("\n".join(messages))
    return answer


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
    app.run(port=5000, debug=True)
