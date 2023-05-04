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
    # summarize the customer chat into one question for better search
    question = await summarize_question(customer_chat)
    cprint(question, "magenta")

    # take the question and search the most relevant embeddings
    context_sections = get_context_sections(question)

    # construct the prompt

    # could use gptrim here to save tokens
    # system_prompt = trim(system_prompt)

    # could up this limit if using gpt-4
    # could also use tiktoken to count tokens instead of characters
    if len(customer_chat) + len(context_sections) > 10000:
        truncate_at = 10000 - len(customer_chat)
        context_sections = context_sections[:truncate_at] + "..."

    prompt = (
        system_prompt
        + "\nHelp article sections:\n"
        + context_sections
        + "\n--\nChat so far:\n"
        + customer_chat
        + "\nRep:\n<Reply in HTML>"
    )
    messages = [{"role": "user", "content": prompt}]
    cprint(prompt, "blue")

    # generate the reply
    loop = asyncio.get_event_loop()
    chat_completion = await loop.run_in_executor(None, get_chat_completion, messages)
    return chat_completion


def get_context_sections(customer_chat):
    search_results = collection.query(query_texts=[customer_chat], n_results=10)
    with session_scope() as db_session:
        sections = (
            db_session.query(Section)
            .filter(Section.checksum.in_(search_results["ids"][0]))
            .all()
        )
        context_sections = "\n-\n".join([section.content for section in sections])
    return context_sections


async def summarize_question(customer_chat):
    # send chat to openai to summarize
    loop = asyncio.get_event_loop()
    system_prompt = """You are part of a customer service team. Distill the given customer service chat to just the question being currently asked, so that your colleagues have an easier time answering it."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": customer_chat})
    question = await loop.run_in_executor(None, get_chat_completion, messages)
    return question


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Answer customer questions.")
    parser.add_argument("question", help="The customer question to be answered.")
    try:
        args = parser.parse_args()
        get_answer(args.question)
    except SystemExit:
        get_answer("how can i enter scores?")
