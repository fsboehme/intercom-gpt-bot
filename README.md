# IntercomGPT

ChatGPT as your Intercom teammate ... and it knows all your help articles.

Intercom API + Open AI API + Chroma.

Not surprisingly, GPT-4 does quite a bit better than GPT-3.5, so ideally try and get access to the GPT-4 API.

## Setup

Copy `.env.sample` to `.env` and enter your API Keys, company name, account_id for the intercom account from which you want to send replies (recommend setting up a new one that looks like a bot so people know what they're dealing with).

I would start with `TEST_MODE=true` so it posts internal notes instead of replying directly to the customer at first. This will allow you to assess its performance and tweak your articles as needed.

Install requirements:

    pip install -r requirements.txt

Generate embeddings from your articles (fetches all your articles from the Intercom API and runs them through Open AI the Embeddings API):

    python make_embeddings.py

Simply run this again after making changes to articles and it will update any changes. (Also runs on each server start.)

### Run locally

In a terminal window run

    python main.py

In another terminal window run

    ngrok http 127.0.0.1:5000

Set up your webhook in Intercom developer hub > webhooks.

- Paste the ngrok forwarding URL + /webhook for the _Endpoint URL_.
- Under _Topics_, subscribe to
  - conversation.user.created
  - conversation.user.replied

### Deploy

Chroma, unfortunately, is too big for a free Vercel instance. I'll look into replacing it with something lighter.

In a production environment, you'll need Hypercorn:

    pip install hypercorn

## To do:

- replace chroma with something lighter
- cancel the open ai api request when customer replies again before gpt reply is posted
