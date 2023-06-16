import asyncio
from termcolor import cprint
from api.openai import OPENAI_MODEL, get_chat_completion
from api.chroma import collection
from make_embeddings import Section, session_scope
import argparse

from prompt import system_prompt

# from gptrim import trim
from dotenv import load_dotenv

load_dotenv()


async def get_answer(messages, skip_prep=False):
    if not skip_prep:
        # summarize the customer chat into one question for better search
        question = await summarize_question(messages)
        if "UNCLEAR" in question:
            question = "\n".join([m["content"] for m in messages])
        cprint(question, "magenta")

        # take the question and search the most relevant embeddings
        context_sections = get_context_sections(question)

        if OPENAI_MODEL == "gpt-4":
            max_chat_length = 20000
        else:
            max_chat_length = 10000
        # could use tiktoken to count tokens instead of characters
        if len(messages) + len(context_sections) > max_chat_length:
            truncate_at = max_chat_length - len(messages)
            context_sections = context_sections[:truncate_at] + "..."

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": "Help article sections:\n" + context_sections,
            },
        ] + messages
    cprint(messages, "blue")

    # generate the reply
    loop = asyncio.get_event_loop()
    chat_completion, messages = await loop.run_in_executor(
        None, get_chat_completion, messages
    )
    return chat_completion, messages


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


async def summarize_question(messages):
    # send chat to openai to summarize
    loop = asyncio.get_event_loop()
    system_prompt = """You are part of a customer service team. Distill the given customer service chat to just the question being currently asked, so that your colleagues have an easier time answering it. If you can't determine the question that is being asked, just say 'UNCLEAR'. Only return the summarized question without any intro or quotation marks, i.e. do not say \"The question being asked is: 'Can I speak to a human please?'\" but just \"Can I speak to a human please?\"."""
    messages = [{"role": "system", "content": system_prompt}] + messages
    question, messages = await loop.run_in_executor(
        None, lambda: get_chat_completion(messages, functions=None)
    )
    return question["content"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Answer customer questions.")
    parser.add_argument("question", help="The customer question to be answered.")
    try:
        args = parser.parse_args()
        asyncio.run(
            get_answer([{"role": "user", "content": "User: " + args.question}])
        )[0]
    except SystemExit:
        # asyncio.run(get_answer("User: how do i enter scores?"))
        asyncio.run(
            get_answer(
                [
                    {
                        "role": "user",
                        "content": "User: how do i make a schedule for 9 teams?",
                    }
                ]
            )
        )[0]
