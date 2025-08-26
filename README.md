# Gemini Autonomous Agent

This project contains a multi-agent autonomous system powered by Gemini. It can plan, review, execute, and reflect on tasks to achieve a high-level mission.

## Setup

1.  **Docker**: Ensure you have Docker installed and running on your system.
2.  **API Key**: You need a Google AI (Gemini) API key.

## How to Run

1.  **Navigate to Project Directory**:
    ```bash
    cd gemini-autonomous-agent
    ```

2.  **Create an Environment File**: Create a file named `.env` in this directory to store your secrets.
    ```
    GOOGLE_API_KEY=your_google_api_key_here

    # Optional: For Netlify deploys
    # NETLIFY_AUTH_TOKEN=your_netlify_auth_token
    # NETLIFY_SITE_ID=your_netlify_site_id
    ```

3.  **Build the Docker Image**:
    ```bash
    docker build -t gemini-agent .
    ```

4.  **Run the Docker Container**:
    ```bash
    docker run -d -p 10000:10000 --env-file .env --name gemini-agent-container gemini-agent
    ```
    - `-d`: Run in detached mode.
    - `-p 10000:10000`: Map the container's port 10000 to your host's port 10000.
    - `--env-file .env`: Load the environment variables from the `.env` file.
    - `--name`: Give the container a memorable name.

## How it Works

- The container starts and launches `server.js` along with five Python-based microservices for the different agents (Planner, Reviewer, etc.).
- You can trigger a work loop by sending a POST request to the cron endpoint, or configure a service like `cron` or Render.com to do it for you.
  ```bash
  curl -X POST http://localhost:10000/cron/loop
  ```
- The system will then perform one full Plan -> Review -> Execute -> Reflect cycle.

## Viewing the Dashboard

Once the agent has run a few loops, you can view the telemetry dashboard by opening your browser to:
[http://localhost:10000](http://localhost:10000)

This will show a list of all completed loops, with links to detailed pages showing the plan, review, execution report, and reflection for each one.
