# Simple Chatbot (With CI/CD in Google Cloud)

## Prerequisites

1.  **Google Cloud Project:**
    - A Google Cloud Platform project.
    - Billing enabled for the project.
2.  **Docker:** Installed locally if you want to build/run the image locally.
3.  **Python & `uv`:** Python 3.11+ and `uv` (or `pip`) for local development.
4.  **Gemini API Key:**
    - Obtain an API key for the Gemini API from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Local Development & Setup

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Set up a virtual environment (optional if you don't use `uv`):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Configure local Gemini API Key:**
    Rename `.env.template` to `.env` and replace `YOUR_GEMINI_API_KEY_HERE` with your API key.

4.  **Run the Streamlit app locally:**
    ```bash
    uv run streamlit run app.py
    # Or: streamlit run app.py
    ```
    The application will be available at `http://localhost:8501`.

## Deployment to Google Cloud Run using Cloud Build

### Phase 1: Local Preparations & Sanity Checks

1.  **Ensure all files are committed and pushed to GitHub:**

    - `app.py` (Streamlit application)
    - `requirements.txt` (defining dependencies)
    - `Dockerfile` (as configured in previous steps, using `uv sync`)
    - `cloudbuild.yaml` (as configured, with correct substitutions for `_GCR_HOSTNAME`)
    - `.gitignore`

2.  **(Optional but Recommended) Test Docker Build Locally:**
    Open your terminal in the project root and run:
    ```bash
    docker build -t gemini-chatbot-test .
    ```
    If this completes successfully, it's a good sign the `Dockerfile` and dependency setup are correct. You can even try running it:
    ```bash
    docker run -p 8501:8501 -e PORT=8501 gemini-chatbot-test
    ```
    Then open `http://localhost:8501` in your browser. (You won't have the API key here unless you pass it, but the app should start).

### Phase 2: Google Cloud Platform Setup

1.  **Select or Create a GCP Project:**

    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Ensure you have a project selected, or create a new one. Make sure billing is enabled for this project.

2.  **Enable Necessary APIs:**

    - In the Cloud Console, search for and enable the following APIs:
      - **Cloud Build API**
      - **Cloud Run API**
      - **Cloud Run Admin API**
      - **Artifact Registry API** (This is where your Docker images will be stored. It's preferred over the older Container Registry).
      - **Secret Manager API**
      - **IAM API** (Identity and Access Management - usually enabled by default)

3.  **Store your Gemini API Key in Secret Manager:**

    - Navigate to **Security > Secret Manager** in the Cloud Console.
    - Click **"Create Secret"**.
    - **Name:** `gemini-api-key-secret` (this _must_ match the name used in your `cloudbuild.yaml`'s `--set-secrets` flag).
    - **Secret value:** Paste your actual Gemini API key.
    - Leave other settings as default and click **"Create secret"**.

4.  **Create an Artifact Registry Docker Repository:**

    - Navigate to **CI/CD > Artifact Registry** in the Cloud Console.
    - Click **"Create Repository"**.
    - **Name:** e.g., `gemini-chatbot-repo` (you can choose any name).
    - **Format:** Docker.
    - **Mode:** Standard.
    - **Location Type:** Region.
    - **Region:** Select the _same region_ you plan to deploy your Cloud Run service to (e.g., `us-central1`). This is important for performance and potential cost savings.
    - Click **"Create"**.
    - **Note the path:** After creation, the path will look like `REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO_NAME`.
      - For example: `us-central1-docker.pkg.dev/my-gcp-project-id/gemini-chatbot-repo`
      - The `_GCR_HOSTNAME` in your `cloudbuild.yaml` should be the first part: `us-central1-docker.pkg.dev`.
      - The image name in `cloudbuild.yaml` will effectively become: `us-central1-docker.pkg.dev/YOUR_PROJECT_ID/gemini-chatbot-repo:${COMMIT_SHA}` if your `_SERVICE_NAME` is `gemini-chatbot-repo` and your repository _is part of the image path implicitly defined by Artifact Registry_.

5.  **Configure IAM Permissions for the Cloud Build Service Account:**
    The Cloud Build service account needs permissions to perform actions on your behalf.
    - Navigate to **IAM & Admin > IAM**.
    - Find the principal (service account) named `[YOUR_PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`.
      - You can find `YOUR_PROJECT_NUMBER` on the GCP Console Dashboard.
    - Click the pencil icon (Edit principal) next to it.
    - Click **"+ ADD ANOTHER ROLE"** and add the following roles:
      - **Cloud Run Admin:** (<code>roles/run.admin</code>) - Allows Cloud Build to deploy and manage Cloud Run services.
      - **Service Account User:** (<code>roles/iam.serviceAccountUser</code>) - Allows Cloud Build to deploy Cloud Run services that can act as (use the identity of) other service accounts (typically the Compute Engine default service account).
      - **Artifact Registry Writer:** (<code>roles/artifactregistry.writer</code>) - Allows Cloud Build to push images to your Artifact Registry repository. (You can scope this to the specific repository if desired).
      - **Secret Manager Secret Accessor:** (<code>roles/secretmanager.secretAccessor</code>) - Allows Cloud Build to access the Gemini API key from Secret Manager during deployment. (You can scope this to the specific secret).
    - Click **"Save"**.

### Phase 3: Set Up Cloud Build Trigger

1.  **Connect Your GitHub Repository to Cloud Build:**

    - Navigate to **CI/CD > Cloud Build > Triggers**.
    - If you haven't connected a source repository before, you might see a "Connect repository" wizard. Follow the prompts to connect your GitHub account and select the repository where your code resides.
    - If you've connected before, click **"Manage repositories"** at the top or **"Connect repository"** if prompted.
    - Select "GitHub" as the source.
    - Authenticate with GitHub and authorize Google Cloud Build.
    - Select your GitHub account/organization and then select the specific repository containing your Streamlit app code.
    - Click **"Connect"**. Then click **"Done"**.

2.  **Create the Trigger:**
    - On the Cloud Build Triggers page, click **"Create trigger"**.
    - **Name:** e.g., `deploy-gemini-chatbot-main`
    - **Description:** (Optional) e.g., `Deploys Gemini Streamlit app to Cloud Run on push to main`
    - **Event:** "Push to a branch"
    - **Source > Repository:** Select the GitHub repository you just connected.
    - **Source > Branch:** `^main$` (This is a regex that matches the "main" branch exactly. Use `^master$` if your default branch is "master").
    - **Configuration > Type:** "Cloud Build configuration file (yaml or json)"
    - **Configuration > Location:** "Repository"
    - **Configuration > Cloud Build configuration file location:** `cloudbuild.yaml` (If it's in the root of your repo. If it's in a subdirectory, specify `subdir/cloudbuild.yaml`).
    - **Advanced > Substitution variables:** This is important to match your `cloudbuild.yaml`.
      - Click **"+ ADD VARIABLE"** for each:
        - Variable: `_SERVICE_NAME` Value: `gemini-chatbot-repo` (or whatever you used in `cloudbuild.yaml` and for your Artifact Registry repo name)
        - Variable: `_REGION` Value: `us-central1` (or your chosen region, ensure it matches Artifact Registry region and `cloudbuild.yaml`)
        - Variable: `_GCR_HOSTNAME` Value: `us-central1-docker.pkg.dev` (Adjust region if your Artifact Registry is elsewhere. This is the host for Artifact Registry, not `gcr.io` unless you're using the older Container Registry).
    - Click **"Create"**.

### Phase 4: First Deployment (Triggered by a Push)

1.  **Make a small commit and push to your `main` branch:**
    For example, add a comment to `app.py` or update a `README.md`.

    ```bash
    git add .
    git commit -m "Trigger initial Cloud Build deployment"
    git push origin main
    ```

2.  **Monitor the Build in Cloud Build:**

    - Go to **CI/CD > Cloud Build > History** in the GCP Console.
    - You should see a new build running for your repository and branch.
    - Click on it to see the build logs and steps. It will:
      - Clone your repository.
      - Build the Docker image (using `docker build ...` as defined in `cloudbuild.yaml`).
      - Push the image to Artifact Registry.
      - Deploy the image to Cloud Run (using `gcloud run deploy ...`).

3.  **Check Cloud Run Service:**
    - Once the build completes successfully, navigate to **Compute > Cloud Run**.
    - You should see your service (e.g., `gemini-chatbot-repo`) listed.
    - Click on the service name.
    - The service URL will be displayed at the top. Click it to open your deployed Streamlit application!
    - Check the "Logs" tab in Cloud Run for your service if you encounter any runtime issues.

### Phase 5: Verification and Future Updates

1.  **Test Your Deployed App:** Interact with your chatbot to ensure it's working as expected and can call the Gemini API.
2.  **Automatic Updates:** Now, every time you push a commit to the `main` branch of your connected GitHub repository, the Cloud Build trigger will automatically:
    - Rebuild your Docker image with the latest code.
    - Push the new image to Artifact Registry.
    - Deploy a new revision to your Cloud Run service with the updated image.

---

### Troubleshooting Tips:

- **Build Failures (Cloud Build):** Check the build logs in Cloud Build carefully. Common issues:
  - Incorrect `Dockerfile` commands.
  - Typos in `cloudbuild.yaml`.
  - IAM permission errors (Cloud Build service account missing a role).
  - `uv` or dependency installation issues.
- **Deployment Failures (Cloud Run step in Cloud Build):**
  - IAM permission errors (Cloud Build SA missing Cloud Run Admin or Service Account User).
  - Incorrect image path.
  - Cloud Run service configuration issues.
- **Application Not Starting/Errors on Cloud Run:**
  - Check the logs for your service in **Cloud Run > [Your Service] > Logs**.
  - Ensure the `GEMINI_API_KEY` environment variable is correctly injected (you can see environment variables in the Cloud Run service revision details).
  - Port issues: The `Dockerfile` `EXPOSE`s 8501, and the `CMD` uses `$PORT`. Cloud Run sets `$PORT` and expects the app to listen on it. The `cloudbuild.yaml` also specifies `--port=8501` for the service definition which is good.
  - Application code errors.

## Understanding the Files

- **`app.py`:**

  - The core Streamlit application.
  - Manages session state for chat history and model selection.
  - Makes requests to the Gemini API (`call_gemini`).
  - Streams responses from the API (`response_generator`).
  - Uses Streamlit's `st.chat_message`, `st.chat_input`, and `st.write_stream`.

- **`Dockerfile`:**

  - Uses `python:3.11-slim` as the base image.
  - Installs `uv` for faster package installation.
  - Sets environment variables `PYTHONUNBUFFERED`, `PIP_NO_CACHE_DIR`, `PIP_DISABLE_PIP_VERSION_CHECK`, `UV_SYSTEM_PYTHON`, and `PORT`.
  - Copies `requirements.txt` and installs dependencies.
  - Copies the application code.
  - Exposes port `8501` (which Streamlit will use, dynamically set by Cloud Run's `$PORT` env var).
  - The `CMD` uses `uv run streamlit run ...` to start the application. Cloud Run's `$PORT` environment variable is used to set the server port.
    - `--server.enableCORS false` and `--server.enableXsrfProtection false`: These are often necessary for Streamlit apps behind proxies or load balancers like Cloud Run.
    - `--server.headless true`: Recommended for running Streamlit in a headless environment.

- **`requirements.txt`:**
  Lists the Python dependencies:

  ```
  streamlit
  requests
  # Add any other direct dependencies here
  ```

- **`cloudbuild.yaml`:**
  Defines the CI/CD steps for Google Cloud Build:
  1.  **Build Docker Image:** Builds the Docker image using the `Dockerfile`.
  2.  **Push Docker Image:** Pushes the built image to Artifact Registry (or GCR) tagged with the commit SHA.
  3.  **Deploy to Cloud Run:** Deploys the image to Cloud Run.
      - `--platform=managed`: Specifies managed Cloud Run.
      - `--allow-unauthenticated`: Makes the service publicly accessible. Remove or configure IAM for authentication if needed.
      - `--port=8501`: Informs Cloud Run that the container expects traffic on port 8501.
      - `--set-secrets=GEMINI_API_KEY=gemini-api-key-secret:latest`: Mounts the Gemini API key from Secret Manager.
      - `--command=uv` and `--args=run,streamlit,run,app.py,--server.port,${PORT},...`: Overrides the Docker `CMD` to explicitly run Streamlit with `uv` and ensure it listens on the port provided by Cloud Run (`${PORT}`). This provides fine-grained control over the startup command.

This setup provides a robust foundation for developing and deploying a Gemini-powered Streamlit chatbot on Google Cloud.
