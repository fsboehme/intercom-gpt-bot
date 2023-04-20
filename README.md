# IntercomGPT

ChatGPT as your Intercom teammate ... and it knows all your help articles.

Intercom API + Open AI API + Chroma.

    Not finished. Work in progress.

## Setup

Copy `.env.sample` to `.env` and enter your API Keys, company name, account_id for the intercom account from which you want to send replies (recommend setting up a new one that looks like a bot so people know what they're dealing with).

Install requirements:

    pip install -r requirements.txt

Generate embeddings from your articles (fetches all your articles from the Intercom API and runs them through Open AI the Embeddings API):

    python make_embeddings.py

Simply run this again after making changes to articles and it will update any changes.

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

- more testing and prompt optimization
- add webhook receiver for new/updated articles
- switch Chroma to using client/server mode
