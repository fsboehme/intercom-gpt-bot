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

That's all you can do right now.

## Next:

- add response functionality
- add webhook receiver for new messages
- add webhook receiver for new/updated articles
- switch Chroma to using client/server mode
