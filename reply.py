import asyncio
import os
from termcolor import cprint
from api_openai import get_chat_completion
from chroma import collection
from make_embeddings import Article, Section, session_scope
import argparse

# from gptrim import trim
from dotenv import load_dotenv

load_dotenv()

COMPANY = os.getenv("COMPANY")


async def get_answer(customer_chat):
    # take the customer's question and search the most relevant embeddings
    search_results = collection.query(query_texts=[customer_chat], n_results=10)
    with session_scope() as db_session:
        sections = (
            db_session.query(Section)
            .filter(Section.checksum.in_(search_results["ids"][0]))
            .all()
        )
        context_sections = "\n-\n".join([section.content for section in sections])

    # construct the prompt
    system_prompt = f"You are a friendly {COMPANY} representative. Use the info in the following sections from {COMPANY} help articles to respond to the chat below. Include links to articles you used in your answer. If you are unsure and the answer is not explicitly written in the articles reply 'PASS'. Avoid repeating what has already been said. If question has been answered and no further info requested, say 'CLOSE'. If user only said hi or stated they have a question, prompt them to state their question. Give an easily readable answer in HTML."
    # *Always* show your source by linking to the relevant article.

    # could use gptrim here to save tokens
    # system_prompt = trim(system_prompt)

    if len(context_sections) > 8000:
        context_sections = context_sections[:8000] + "..."

    prompt = (
        system_prompt
        + "\nHelp article sections:\n"
        + context_sections
        + "\n--\nChat:\n"
        + customer_chat
        + "\nRep:"
    )
    messages = [{"role": "user", "content": prompt}]
    cprint(prompt, "blue")

    # generate the reply
    loop = asyncio.get_event_loop()
    chat_completion = await loop.run_in_executor(None, get_chat_completion, messages)
    return chat_completion


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Answer customer questions.")
    parser.add_argument("question", help="The customer question to be answered.")
    try:
        args = parser.parse_args()
        get_answer(args.question)
    except SystemExit:
        get_answer("how can i enter scores?")
