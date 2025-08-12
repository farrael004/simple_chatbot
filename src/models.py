import streamlit as st
import requests
import json

response = requests.get("https://openrouter.ai/api/v1/models")
models = json.loads(response.content)

if "data" in models:
    models = models["data"]
    # Keep only models where price is lower than 0.001
    models = [
        m
        for m in models
        if float(m["pricing"]["prompt"]) < 0.00000001
        and float(m["pricing"]["completion"]) < 0.00000001
    ]

    # Change names to remove "(free)"
    for m in models:
        m["name"] = m["name"].replace(" (free)", "")

    model_names = [m["name"] for m in models]
else:
    st.error("Failed to fetch models from OpenRouter")
    st.stop()
    models = []
