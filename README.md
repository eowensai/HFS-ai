# HFS AI Assistant

A self-hosted, UW-branded chat interface for interacting with local Large Language Models (LLMs). This application provides a clean, professional front-end with support for document and image analysis.

*(It is highly recommended to add a screenshot of the running application here to give an immediate visual overview.)*
`![Application Screenshot](<path-to-your-screenshot.png>)`

---

## Core Features

* **🤖 AI Assistant:** Provides a direct, streaming chat interface with a local LLM running on [Ollama](https://ollama.com/).
* **📄 Document Upload:** Supports text extraction from files like PDF and DOCX using Apache Tika.
* **🖼️ Multimodal Support:** Allows images to be included as part of a query for visual analysis.
* **🎨 UW-Branded Interface:** A clean, minimal UI with a custom University of Washington theme that is locked to light mode for consistency.
* **🔒 Ephemeral & Secure:** Chat sessions are not stored on the server. The architecture is designed to keep all services on the local network.

## Architecture Overview

This application uses a hybrid architecture that leverages a Windows host for the LLM and a WSL2 environment for the containerized web application.

* **Windows Host:**
    * **Ollama Service:** Manages and serves the LLM.
* **WSL2 (Ubuntu) Host:**
    * **Docker Engine:** Manages all supporting services.
        * **HFS-ai Kiosk (`kiosk-app`):** The Streamlit web front-end.
        * **Apache Tika (`tika-server`):** The document parsing service.

## Technology Stack

* **Frontend:** Python 3.11 / Streamlit
* **LLM Service:** Ollama
* **Document Parsing:** Apache Tika
* **Containerization:** Docker / Docker Compose v2

---

## Quick Start Guide

This guide assumes you have already completed the full setup and environment hardening process.

### Prerequisites

**You must first follow the complete setup instructions in the [Production Deployment Guide](./path-to-your/Production-Deployment-Guide.md).** This `README` is only for starting/stopping the application after the environment has been configured.

### Running the Application

1.  **Start the Kiosk Service:**
    Navigate to the project directory in your WSL terminal and run:
    ```bash
    # From ~/kiosk-llm
    docker compose up -d
    ```
    *Note: The Tika service is managed by `systemd` and should start automatically with WSL. This command will start the `kiosk-app`.*

2.  **Access the Interface:**
    Open a web browser on your Windows host and go to:
    **[http://localhost:8501](http://localhost:8501)**

### Stopping the Application

To stop the `kiosk-app` container:
```bash
# From ~/kiosk-llm
docker compose down

### Configuration
Runtime Configuration: Key settings like the LLM IP address (LLM_BASE_URL) and model name (LLM_MODEL_NAME) are managed as environment variables in the docker-compose.yml file.
Theme & Styling: The visual theme is controlled by .streamlit/config.toml (for the base theme) and theme.css (for all specific UW branding).

###Full Documentation
For complete, end-to-end instructions on environment setup, deployment, troubleshooting, and architectural details, please see the Production Deployment Guide.

###Support
For issues or questions, please contact eko@uw.edu.
