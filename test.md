# EphemerAl: A Self-Hosted Web UI for Local LLM Document Analysis with Ollama

EphemerAl is a lightweight, open-source interface for running Google's Gemma 3 LLM locally on your hardware. Designed for privacy-focused users, it enables self-hosted AI interactions with documents and images without cloud dependencies, data leakage, or persistent storage. Ideal for developers seeking a secure, multimodal LLM tool for internal workflows, knowledge management, or experimentation.

![EphemerAl in action: A self-hosted local LLM web UI analyzing documents via Ollama and Gemma 3 integration](static/ephemeral_demo.gif)
*Alternative text for SEO: Screenshot of EphemerAl, a Docker-based self-hosted AI assistant for local LLM document Q&A and image analysis using Ollama.*

## Problem It Solves
In environments demanding high privacy and control—such as workplaces or personal labs—cloud-based AI services pose risks related to data exposure and costs. EphemerAl addresses this by providing a fully local, ephemeral AI chat interface that supports document parsing (via Apache Tika) and image analysis (via Gemma 3's multimodal capabilities). Conversations are erased on refresh, ensuring no trace remains, while leveraging consumer-grade NVIDIA GPUs for efficient, on-premises inference.

## Core Features
- **Local LLM Integration:** Real-time chat powered by Google's Gemma 3 (12B or 27B quantized models) via Ollama, enabling generative AI tasks like question-answering and summarization without internet access.
- **Document Upload Support:** Handles over 100 file types (e.g., PDFs, docs, spreadsheets) through Apache Tika, injecting parsed text directly into queries for retrieval-augmented generation (RAG).
- **Multimodal Capabilities:** Analyzes images alongside text using Gemma 3's built-in vision support, ideal for document-understanding or visual Q&A.
- **Customizable UI:** Minimal Streamlit-based interface with optional branding (e.g., logo), themes, and timezone-aware timestamps for professional use.
- **Ephemeral Design:** No session persistence, user accounts, or data logging—conversations vanish on refresh or "New Conversation" for maximum privacy.
- **Easy Deployment:** Containerized setup with Docker Compose, supporting WSL2 on Windows for quick self-hosting on local networks.

## Technical Stack
- **Core Framework:** Python 3.11 with Streamlit for the web frontend.
- **LLM Backend:** Ollama serving Gemma 3 (instruction-tuned, quantized models) with CUDA acceleration for NVIDIA GPUs.
- **Document Parsing:** Apache Tika server for extracting text from diverse file formats.
- **Containerization:** Docker and Docker Compose for isolated, reproducible deployment.
- **Environment:** WSL2 on Windows 11 Pro/Enterprise; supports multi-GPU configurations.
- **Dependencies:** Minimal libraries including requests, pytz, tika, openai (client), and pillow.

## System Requirements
- **OS:** Windows 11 Pro or Enterprise (fully updated).
- **GPU:** Discrete NVIDIA GPU (30-series or newer recommended; 12GB+ VRAM for Gemma 3 12B, 24GB+ for 27B).
- **Driver:** Latest WHQL NVIDIA GPU driver.
- **Pro Tip:** Connect your monitor to integrated graphics (if available) to free up ~0.5-1GB VRAM on the NVIDIA GPU.

## Deployment
Follow the step-by-step instructions in [System Deployment Guide.md](System%20Deployment%20Guide.md). No prior Docker or WSL experience required—commands are copy-paste ready.

1. Set up WSL2 with Ubuntu 24.04.
2. Install Docker and NVIDIA Container Toolkit.
3. Create project files (e.g., Dockerfile, docker-compose.yml).
4. Build and deploy containers.
5. Download and configure the Gemma 3 model in Ollama.
6. Access at http://localhost:8501 (or network IP for remote devices).

For unattended/kiosk mode, configure auto-start via the provided PowerShell script.

## Access the Interface
- **Local Server:** http://localhost:8501
- **Network Devices:** http://<windows_host_ip_address>:8501

## Stopping the Application
In an Administrator PowerShell:
```
# Admin PowerShell
wsl --shutdown
```

Restart by running `wsl` or rebooting.

## Known Issues
- Mobile rendering may be suboptimal.
- Sidebar minimization requires a refresh to undo.
- Long queries may overlap the input arrow before wrapping.
- Attachments vanish visually post-submission but remain in context.
- No explicit handling for exceeding model context limits (Gemma 3 supports large windows; monitor VRAM usage).

## Support
This project is shared as-is for community use. For issues:
- Paste errors into an AI assistant with screenshots and your technical level.
- Attach relevant files (e.g., from section 4 of the Setup Guide) for analysis.

License: [MIT](whatever parts are mine to license).
