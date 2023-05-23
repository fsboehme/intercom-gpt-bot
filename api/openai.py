import time
import openai
import os
from dotenv import load_dotenv
from termcolor import cprint

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDINGS_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-ada-002")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.25))


def get_embedding(text, model=OPENAI_EMBEDDINGS_MODEL):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input=[text], model=model)["data"][0]["embedding"]


def get_chat_completion(messages, model=OPENAI_MODEL, temperature=OPENAI_TEMPERATURE):
    while True:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
        except (openai.error.RateLimitError, openai.error.APIError) as e:
            cprint("{e}", "red")
            # wait 5 seconds and try again
            time.sleep(5)
            continue
        break
    messages.append(response.choices[0].message)
    cprint("OpenAI response:\n" + response.choices[0].message.content, "yellow")
    return response.choices[0].message.content
