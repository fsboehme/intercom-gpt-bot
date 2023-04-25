import asyncio
from termcolor import cprint
from api.openai import get_chat_completion
from api.chroma import collection
from make_embeddings import Section, session_scope
import argparse

from prompt import system_prompt

# from gptrim import trim
from dotenv import load_dotenv

load_dotenv()


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
    # Avoid repeating what has already been said.
    # *Always* show your source by linking to the relevant article.

    # could use gptrim here to save tokens
    # system_prompt = trim(system_prompt)

    if len(customer_chat) + len(context_sections) > 10000:
        truncate_at = 10000 - len(customer_chat)
        context_sections = context_sections[:truncate_at] + "..."

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
