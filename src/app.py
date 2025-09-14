import streamlit as st
from openai import Stream
from openai.types.chat import ChatCompletionChunk

from document_reader import read_uploaded_file
from llm import call_llm
from prompt import (
    trim_messages_to_token_limit,
    build_system_prompt,
    build_docs_context,
    build_search_context,
)
from models import model_names, models

st.set_page_config(page_title="RAG Chatbot", page_icon="💬")

if "history" not in st.session_state:
    st.session_state.history = []  # list of {"role": "user"/"assistant", "content": str}
if "uploaded_texts" not in st.session_state:
    st.session_state.uploaded_texts = []
if "model" not in st.session_state:
    st.session_state.model = model_names[0]

st.title("RAG Chatbot")
st.caption("Use the settings on the left to enable RAG functionality.")

with st.sidebar:
    st.header("Settings")
    st.session_state.model = st.selectbox("Model", model_names, index=0)
    temperature = st.slider(
        "Temperature", min_value=0.0, max_value=1.0, value=1.0, step=0.01
    )
    st.markdown("---")
    st.subheader("Web Search")
    do_search = st.checkbox("Use web search for next message", value=False)
    search_query_override = st.text_input("Search query override (optional)", "")
    st.markdown("---")
    st.subheader("Document context")
    uploaded_files = st.file_uploader(
        "Upload documents (.pdf, .docx, .txt)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
    )
    col1, col2 = st.columns(2)
    if col1.button("Ingest uploaded files"):
        texts = []
        for f in uploaded_files or []:
            with st.spinner(f"Reading {f.name}..."):
                t = read_uploaded_file(f)
                if t.strip():
                    texts.append(t)
        if texts:
            st.session_state.uploaded_texts.extend(texts)
            st.success(f"Added {len(texts)} documents to context.")
        else:
            st.warning("No text extracted from selected files.")
    if col2.button("Clear ingested files"):
        st.session_state.uploaded_texts = []
        st.info("Cleared all ingested document context.")
    # Display current context summary
    with st.expander("Current document context summary", expanded=False):
        doc_count = len(st.session_state.uploaded_texts)
        st.write(f"Documents in context: {doc_count}")
        if doc_count > 0:
            sample = "\n\n---\n\n".join(
                [t[:200] for t in st.session_state.uploaded_texts[:3]]
            )
            st.text(sample + ("\n\n... (truncated)" if doc_count > 3 else ""))
    st.markdown("---")
    if st.button("Clear chat history"):
        st.session_state.history = []
        st.info("Chat history cleared.")

# Chat UI
for msg in st.session_state.history:
    if msg["role"] == "user":
        st.chat_message("user").markdown(msg["content"])
    else:
        st.chat_message("assistant").markdown(msg["content"])

user_input = st.chat_input("Type your message...")

if user_input:
    st.session_state.history.append({"role": "user", "content": user_input})
    st.chat_message("user").markdown(user_input)

    # Find model based on its name
    model = next((m for m in models if m["name"] == st.session_state.model), None)
    if not model:
        raise ValueError(f"Unknown model: {st.session_state.model}")

    # Optional web search
    search_block = ""
    search_results = []
    if do_search:
        search_block = build_search_context(
            search_query_override, st.session_state.history, model
        )

    # Build messages

    docs_context = build_docs_context(user_input, st.session_state.uploaded_texts)
    context_sections = []
    if search_block:
        context_sections.append(search_block)
    if docs_context:
        context_sections.append("Uploaded Documents:\n" + docs_context)

    context_prefix = "\n\n".join(context_sections).strip()

    system_prompt = build_system_prompt(
        web_search_is_enabled=do_search,
        document_context_is_enabled=(docs_context != ""),
    )

    # Construct the prompt for the assistant with context prefix
    # Strategy: prepend a short assistant-readable context chunk before latest user message
    latest_user = user_input
    if context_prefix:
        augmented_user = f"Question:\n{latest_user}\n\n---\n\nContext:\nYour answer is only allowed to reference information in this context:\n{context_prefix}\n\n---\n\nThe user cannot see the context. Cite and copy the exact link to the relevant documents in the context so the user can verify the answer."
    else:
        augmented_user = latest_user

    # Assemble chat messages
    messages = [{"role": "system", "content": system_prompt}]
    # Include previous turns (excluding last user turn we just added separately)
    prior = st.session_state.history[:-1]
    messages.extend(prior)
    # Replace last user turn with augmented
    messages.append({"role": "user", "content": augmented_user})

    # Trim to token limit
    max_tokens = model["top_provider"]["context_length"]
    messages = trim_messages_to_token_limit(messages, max_tokens)

    # Call model with streaming
    placeholder = st.chat_message("assistant").empty()
    stream_text = ""
    try:
        with placeholder:
            with st.spinner("Thinking..."):
                print(messages)
                stream: Stream[ChatCompletionChunk] = call_llm(
                    messages,
                    model=model,
                    temperature=temperature,
                    stream=True,
                )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    stream_text += delta
                    placeholder.markdown(stream_text)
                # Sleep tiny amount to keep UI responsive
                # time.sleep(0.005)
    except Exception as e:
        stream_text = f"Error: {e}"
        placeholder.markdown(stream_text)

    st.session_state.history.append({"role": "assistant", "content": stream_text})

# Footer
st.markdown("---")
st.caption(
    "This app uses OpenRouter for LLM responses and DuckDuckGo for search. Upload files to enrich context. Please do not upload sensitive data."
)
