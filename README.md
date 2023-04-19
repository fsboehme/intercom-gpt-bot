# IntercomGPT

ChatGPT as your Intercom teammate ... and it knows all your help articles.

Intercom API + Open AI API + Chroma.

    Not finished. Work in progress.

## Setup

Copy `.env.sample` to `.env` and enter your API Keys.

Install requirements:

    pip install -r requirements.txt

Generate embeddings from your articles (fetches all your articles from the Intercom API and runs them through Open AI the Embeddings API):

    python make_embeddings.py

### Run locally

In a terminal window run

    python intercom_webhook.py

In another terminal window run

    ngrok http 127.0.0.1:5000

Set up your webhook in Intercom developer hub > webhooks.

- Paste the ngrok forwarding URL + /webhook for the _Endpoint URL_.
- Under _Topics_, subscribe to
  - conversation.user.created
  - conversation.user.replied

## To do:

- some more testing
- send response back to intercom
- deploy
- add webhook receiver for new/updated articles
- switch Chroma to using client/server mode
