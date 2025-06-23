# Use an official Python runtime as a parent image
FROM python:3.11-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    UV_SYSTEM_PYTHON=true \
    # Streamlit needs a port, Cloud Run provides it via PORT env var
    PORT=8501

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt.
COPY requirements.txt ./

# Install dependencies using uv
RUN uv pip install -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port Streamlit will run on (matches $PORT)
EXPOSE 8501

# Define the command to run the application
#    Cloud Run will set the $PORT environment variable.
#    Using uv run to execute streamlit
CMD uv run streamlit run app.py --server.port ${PORT} --server.enableCORS false --server.enableXsrfProtection false --server.headless true