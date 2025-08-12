import streamlit as st
from typing import List, Dict, Tuple
import tiktoken
from openai.types.chat import ChatCompletion
import json

from search import duckduckgo_search, SEARCH_RESULTS, render_search_block
from embeddings import rag_search
from llm import call_llm


def build_system_prompt(
    web_search_is_enabled: bool, document_context_is_enabled: bool
) -> str:
    prompt = "You are Chatty, a friendly and helpful assistant. If there is insufficient information to answer the user's question, state so and suggest uploading files or enabling web search. Never produce links that are not for the homepage of a well-known source, but feel free to write links present in the context of this conversation. Always direct your answer to the user."
    if document_context_is_enabled:
        prompt += " Use uploaded document context when relevant."
    if web_search_is_enabled:
        prompt += " Use web search when relevant."
        prompt += " Always cite sources in clickable markdown links: [source](https://example.com)."
    return prompt


def build_docs_context(
    user_input: str, uploaded_texts: List[str], top_k: int = 5
) -> str:
    """
    Preferred: build a small, targeted context using retrieval for the current user_input.
    """
    if not uploaded_texts or not user_input:
        return ""
    lines, _ = rag_search(user_input, uploaded_texts, top_k=top_k)
    context = "Retrieved Document Context:\n" + "\n\n".join(lines)
    return context


def build_search_context(search_query_override, chat_history: List[dict], model) -> str:
    if search_query_override:
        query = search_query_override
    else:
        system_prompt = "You are an internet query generator. This is a chat history between a chatbot and the user. You as the query generator must generate a search query based on the conversation history so far."
        user_prompt = f"{json.dumps(chat_history)}\nCreate an internet search query based on the conversation history so far."
        search_chat_history = [
            {"role": "user", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response: ChatCompletion = call_llm(
            messages=search_chat_history, model=model, stream=False
        )
        query = response.choices[0].message.content

        # Remove quotation marks
        query = query.replace('"', "")
    search_block = ""
    if not query:
        return search_block
    with st.spinner("Searching the web..."):
        search_results = duckduckgo_search(query, n=SEARCH_RESULTS)
        if search_results:
            search_block = "Web Search Results:\n" + render_search_block(search_results)
    return search_block


def trim_messages_to_token_limit(
    messages: List[Dict[str, str]], max_tokens: int
) -> List[Dict[str, str]]:
    # Rough trimming strategy: keep system, last N messages until token limit
    total = 0
    kept = []
    # Ensure system first if present
    system_msg = None
    others = []
    for m in messages:
        if m["role"] == "system" and system_msg is None:
            system_msg = m
        else:
            others.append(m)

    if system_msg:
        total += token_len(system_msg.get("content", ""))
        kept.append(system_msg)

    # Walk from end to start for recency
    for m in reversed(others):
        c = m.get("content", "")
        t = token_len(c)
        if total + t <= max_tokens:
            kept.insert(1 if system_msg else 0, m)  # insert after system
            total += t
        else:
            # Try to add truncated version if user or assistant
            if t > 0 and (max_tokens - total) > 100:
                truncated = truncate_by_tokens(c, max_tokens - total)
                kept.insert(
                    1 if system_msg else 0, {"role": m["role"], "content": truncated}
                )
                total = max_tokens
            break
    return kept


def token_len(text: str) -> int:
    return len(encode_tokens(text))


def truncate_by_tokens(text: str, max_tokens: int) -> str:
    toks = encode_tokens(text)
    if len(toks) <= max_tokens:
        return text
    enc = tiktoken.get_encoding("cl100k_base")
    return enc.decode(toks[:max_tokens])


def encode_tokens(text: str, encoding_name: str = "cl100k_base") -> List[int]:
    try:
        enc = tiktoken.get_encoding(encoding_name)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return enc.encode(text or "")
