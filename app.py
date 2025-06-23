import streamlit as st
import requests
from dataclasses import dataclass
import json
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Message:
    role: str
    content: str


def response_generator():
    response_obj = call_gemini(st.session_state.messages)
    # response_obj.raise_for_status() # Already called in call_gemini

    full_json_buffer = ""  # To handle JSON objects potentially split across 'data:' lines (rare for Gemini)
    # but more robustly, Gemini sends one JSON object per 'data:' line.

    for line_bytes in response_obj.iter_lines():
        if not line_bytes:  # Skip keep-alive newlines
            continue

        line_str = line_bytes.decode("utf-8")
        # print(f"SSE Raw Line: {line_str}") # For debugging

        if line_str.startswith("data: "):
            json_payload_str = line_str[len("data: ") :].strip()
            if not json_payload_str:  # Handle empty "data: " lines
                continue

            # For Gemini, each "data:" line typically contains a complete JSON object.
            # If it could span multiple data lines, you'd accumulate json_payload_str
            # into full_json_buffer until a complete object is formed.
            # However, for this API, direct parsing is usually fine.
            try:
                chunk_data = json.loads(json_payload_str)
                # print(f"Parsed JSON: {chunk_data}") # For debugging

                # Extract text based on Gemini's typical response structure
                if "candidates" in chunk_data and chunk_data["candidates"]:
                    candidate = chunk_data["candidates"][0]
                    if (
                        "content" in candidate
                        and "parts" in candidate["content"]
                        and candidate["content"]["parts"]
                    ):
                        text_part = candidate["content"]["parts"][0].get("text", "")
                        if text_part:  # Only yield if there's text
                            yield text_part
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: '{e}' for payload: '{json_payload_str}'")
                # You might want to st.error() or log this more formally
            except KeyError as e:
                print(f"KeyError: '{e}' when processing chunk: {chunk_data}")
        # elif line_str == "[DONE]": # Some APIs send a [DONE] marker, Gemini usually just ends stream.
        #     break
        # else:
        # print(f"Skipping non-data SSE line: {line_str}")


def call_gemini(messages_history):
    model_name = st.session_state["gemini_model"]
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        st.error("GEMINI_API_KEY not found in Streamlit secrets. Please add it.")
        st.stop()
        return None  # Should not proceed

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
    headers = {"Content-Type": "application/json"}

    # Prepare the payload (contents)
    api_contents = []
    for message in messages_history:
        # Ensure role is "user" or "model" as expected by the API
        role = message.role
        if role not in ["user", "model"]:
            print(
                f"Warning: Unexpected role '{role}' found in history. Mapping to 'user'."
            )
            role = "user"  # Or handle as an error
        api_contents.append({"role": role, "parts": [{"text": message.content}]})

    data = {
        "contents": api_contents,
        "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
        # "safetySettings": [ ... ] # Optional: Add safety settings
    }
    # print(f"Sending to Gemini API: {json.dumps(data, indent=2)}") # For debugging the payload

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        # Try to get more details from response if available
        if hasattr(e, "response") and e.response is not None:
            try:
                error_details = e.response.json()
                st.error(f"API Error Details: {error_details}")
            except json.JSONDecodeError:
                st.error(f"API Error Content: {e.response.text}")
        return None  # Indicate failure


st.set_page_config(page_title="Gemini Chatbot", page_icon="🤖")
st.title("💬 Gemini Chatbot")

# Initialize session state variables
if "gemini_model" not in st.session_state:
    st.session_state["gemini_model"] = "gemini-1.5-flash-latest"  # More common default

if "messages" not in st.session_state:
    st.session_state.messages = []  # Start with an empty list of Message objects

with st.sidebar:
    st.session_state["gemini_model"] = st.selectbox(
        "Select Gemini Model",
        [
            "gemini-2.5-flash-lite-preview-06-17",
            "gemini-2.5-flash-preview-04-17",
            "gemini-2.5-pro-preview-05-06",
        ],  # Add more models as needed
        index=1,
    )
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()


# Display chat messages from history
for msg in st.session_state.messages:
    streamlit_role = "user" if msg.role == "user" else "assistant"
    with st.chat_message(streamlit_role):
        st.markdown(msg.content)

# Handle chat input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history and display it
    st.session_state.messages.append(Message(role="user", content=prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get and display assistant's response
    with st.chat_message("assistant"):
        if os.environ.get("GEMINI_API_KEY"):  # Only proceed if API key is set
            streamed_response_generator = response_generator()
            if streamed_response_generator:  # Check if call_gemini was successful
                try:
                    full_response_content = st.write_stream(streamed_response_generator)
                    # Add assistant's full response to history
                    st.session_state.messages.append(
                        Message(role="model", content=full_response_content)
                    )
                except Exception as e:
                    st.error(f"Error during streaming: {e}")
                    # Potentially add a placeholder message to history if streaming fails mid-way
                    st.session_state.messages.append(
                        Message(
                            role="model",
                            content="*An error occurred while generating the response.*",
                        )
                    )
            else:
                # This case is hit if call_gemini returned None due to an error before making the request
                # or if the API key was missing. Error messages would have been shown by call_gemini.
                st.session_state.messages.append(
                    Message(role="model", content="*Could not connect to the API.*")
                )

        else:
            st.error(
                "GEMINI_API_KEY is not configured. Please add it to your Streamlit secrets."
            )
            st.session_state.messages.append(
                Message(role="model", content="*API key not configured.*")
            )
