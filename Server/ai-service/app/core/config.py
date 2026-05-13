import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
load_dotenv()


llm = ChatOllama(
    model="qwen3:8b",
    temperature=1,
)

HOST = os.getenv('DB_HOST')
PORT = os.getenv('DB_PORT')
NAME = os.getenv('DB_NAME')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')