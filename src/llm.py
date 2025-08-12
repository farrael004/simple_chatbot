from typing import List, Dict
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_client() -> OpenAI:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    return client


def call_llm(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.3,
    stream: bool = True,
) -> ChatCompletion | Stream[ChatCompletionChunk]:
    client = get_openrouter_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=stream,
    )
