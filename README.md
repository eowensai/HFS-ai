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
 
## Setup

1. Clone this repository:
   git clone https://github.com/YOUR_USERNAME/hfs-ai-kiosk.git
   cd hfs-ai-kiosk

   cd hfs-ai-kiosk

2. Start all services:
   bashdocker-compose up -d

3. Wait for services to initialize (first run will download models):
   bashdocker-compose logs -f llm-server

4. Access the kiosk at: http://localhost:8501

Architecture
   Streamlit: Web interface (port 8501)
   Ollama: LLM server running Gemma 2 (port 11434)
   Apache Tika: Document parsing (port 9998)

Configuration
   Environment Variables
      LLM_BASE_URL: URL for the LLM server (default: http://llm-server:8080/v1)
      LLM_MODEL_NAME: Model to use (default: gemma2:9b-instruct-fp16)
      TIKA_URL: URL for Tika server (default: http://tika:9998)

Model Parameters
   The following parameters are optimized for Gemma 3:
      Temperature: 1.0
      Top-K: 64
      Top-P: 0.95
      Min-P: 0.0
      XTC Threshold: 1.0
      Repeat Penalty: 1.0

Development
   To run in development mode:
   bash 
      # Install dependencies
      pip install -r requirements.txt

      # Set environment variables
      export LLM_BASE_URL=http://localhost:11434/v1
      export TIKA_URL=http://localhost:9998
      
      # Run the app
      streamlit run kiosk_app.py

Deployment
   For production deployment:
   
   Update docker-compose.yml with production URLs
   Consider using a reverse proxy (nginx) for HTTPS
   Add authentication if needed
   Monitor resource usage (especially RAM for LLM)

Troubleshooting
   LLM Backend Offline
      Check if Ollama is running: docker ps
      View logs: docker-compose logs llm-server
      Ensure model is downloaded: docker exec hfs-llm-server ollama list
   Document Parsing Issues
      Check Tika status: curl http://localhost:9998/tika
      View logs: docker-compose logs tika

Support
   For issues or questions, please email eko@uw.edu 
