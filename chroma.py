import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

client = chromadb.Client(
    Settings(chroma_db_impl="duckdb+parquet", persist_directory="./.chroma")
)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"), model_name="text-embedding-ada-002"
)
collection = client.get_or_create_collection(
    name="articles", embedding_function=openai_ef
)
