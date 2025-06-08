# HFS-AI Kiosk

An AI-powered kiosk application for University of Washington's Housing and Food Services.

## Features

- 🤖 AI assistant powered open weight models (currently gemma 3 12/27b it QAT gguf int4)
- 📄 Document upload support (PDF, DOCX)
- 🖼️ Multimodal support - Image as part of a query
- 🎨 UW-branded interface
- 🔒 Ephemeral - operates via a 'Kiosk mode' (minimal/locked UI)

## Prerequisites

- Docker and Docker Compose
- Llama.cpp docker container in docker network for llm api calls
- Tika docker container in docker network for document to text converstion
- Ubuntu 24.04 with dedicated gpu(s)
- 
## Quick Start

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/hfs-ai-kiosk.git
   cd hfs-ai-kiosk
