import time
import openai
import os
from dotenv import load_dotenv
from termcolor import cprint
import requests

from functions import functions

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDINGS_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-ada-002")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.25))


def get_embedding(text, model=OPENAI_EMBEDDINGS_MODEL):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input=[text], model=model)["data"][0]["embedding"]


def get_chat_completion(
    messages,
    model=OPENAI_MODEL,
    temperature=OPENAI_TEMPERATURE,
    functions=functions,
    function_call=None,
):
    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    if functions is not None:
        kwargs.update({"functions": functions})
    if function_call is not None:
        kwargs.update({"function_call": function_call})
    attempts = 0
    while attempts < 5:
        try:
            response = openai.ChatCompletion.create(**kwargs)
        except (openai.error.RateLimitError, openai.error.APIError) as e:
            cprint("{e}", "red")
            # wait 5 seconds and try again
            time.sleep(5)
            attempts += 1
            continue
        break
    try:
        chat_completion = response["choices"][0]["message"]
    except KeyError:
        cprint(response, "red")
        chat_completion = {
            "role": "system",
            "content": "Sorry, there was an error generating a response.",
        }
    messages.append(chat_completion)
    cprint("OpenAI response:\n" + str(chat_completion), "yellow")
    return chat_completion, messages
