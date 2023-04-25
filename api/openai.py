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
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    messages.append(response.choices[0].message)
    cprint(response.choices[0].message.content, "green")
    return response.choices[0].message.content
