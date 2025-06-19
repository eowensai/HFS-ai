This document captures every step we just walked through to spin up a local development copy of the production HFS-ai Streamlit app.
Keep it in your repo (kiosk-llm-dev/README.md) so anyone can re-create, understand, or troubleshoot the setup.

1 . Purpose
Run a sandbox Streamlit UI on localhost:8502 for safe UI changes.

Reuse the existing Ollama and Apache Tika back-ends so you get full functionality without deploying extra services.

Guarantee prod (localhost:8501) stays online and unaffected.

2 . Prerequisites
Component	Version used in prod	Notes
Docker Engine + Compose	Compose v2.x	Compose now ignores the obsolete version: key (silenced later).
Python base image	python:3.11-slim	
Streamlit	≥ 1.45 (for runOnSave) 
docs.streamlit.io
External network	llm-net — already created for prod containers	
Back-ends	tika-server on llm-net:9998, Ollama on 192.168.87.64:11434	

3 . Directory layout
text
Copy
Edit
/home/eko/
├── kiosk-llm/          # production repo (runs on :8501)
└── kiosk-llm-dev/      # dev repo (runs on :8502)
kiosk-llm-dev is a straight copy of prod, so edits never touch production code.

4 . One-time setup commands
bash
Copy
Edit
# 1. Duplicate the repo
cp -a ~/kiosk-llm ~/kiosk-llm-dev

# 2. Make a dev log folder beside prod logs
mkdir -p ~/kiosk-llm/logs/dev
4.1 Create kiosk-llm-dev/docker-compose.dev.yml
yaml
Copy
Edit
version: "3.8"

services:
  kiosk-app-dev:
    build: ../kiosk-llm            # reuse prod Dockerfile & cache
    container_name: kiosk-app-dev
    restart: unless-stopped

    # Bind to loop-back ONLY → hidden from LAN
    ports:
      - "127.0.0.1:8502:8501"      # host:container

    volumes:
      - ./:/app                    # live-edit source
      - ../kiosk-llm/static:/app/static:ro
      - ../kiosk-llm/logs/dev:/app/logs

    environment:
      - LLM_BASE_URL=http://192.168.87.64:11434/v1
      - LLM_MODEL_NAME=g27:latest
      - TIKA_URL=http://tika-server:9998
      - TIKA_CLIENT_ONLY=true

    command: >
      streamlit run kiosk_app.py
      --server.runOnSave true      # hot-reload on file save
      --server.headless true

    networks:
      - llm-net                    # share back-end network

networks:
  llm-net:
    external: true
Binding the host half of the mapping to 127.0.0.1 keeps the port accessible only from the host OS; nothing on the LAN can reach it. 
docs.docker.com

5 . Start / stop cycle
bash
Copy
Edit
cd ~/kiosk-llm-dev

# Build once, then start in background
docker compose up -d --build

# Follow logs
docker compose logs -f

# Stop dev only
docker compose down
Prod keeps running in its original folder and container.

6 . Smoke-test checklist
URL	What to verify
http://localhost:8501	Prod UI still works.
http://localhost:8502	Dev UI loads.
Text prompt	Returns an answer.
File upload (Tika)	Attachment stays visible and content is parsed.

If file upload silently fails, confirm the dev container is on llm-net:

bash
Copy
Edit
docker inspect -f '{{range .NetworkSettings.Networks}}{{println .NetworkID}}{{end}}' kiosk-app-dev
Re-attach with networks: - llm-net if needed.

7 . Daily workflow
Action	Command
Rebuild after code change	docker compose up -d --build
Live-reload minor tweaks	Just save the file & refresh browser (runOnSave true).
Tail logs	docker compose logs -f
Tear down dev stack	docker compose down

8 . Troubleshooting / FAQs
Symptom	Likely cause	Fix
Port conflict on 8501	Accidentally re-used prod mapping	Ensure only dev maps 127.0.0.1:8502:8501.
File upload disappears	Dev container not on llm-net → cannot resolve tika-server	Add the networks: block & restart.
Slow inference	Shared GPU saturated	Spin up a second Ollama instance, then override LLM_BASE_URL in .env.dev.
Compose warns about version: key	Field now obsolete in Compose v2.26	sed -i '/^version:/d' docker-compose*.yml to silence. 
docs.docker.com

9 . Optional hardening
Pin dependencies

bash
Copy
Edit
docker run --rm kiosk-app-dev pip freeze > requirements.lock
sed -i 's/requirements.txt/requirements.lock/' ../kiosk-llm/Dockerfile
docker compose up -d --build
Run as non-root — see tightened Dockerfile sample in chat history.

Create .env.dev if you want to point dev at alternate back-ends without editing YAML.

Publish dev externally (when needed)

bash
Copy
Edit
cloudflared tunnel run hfs-ai-dev --url http://localhost:8502
10 . Key references
Docker port publishing rules (127.0.0.1 binding limits exposure) 
docs.docker.com

Compose default-network behaviour & external networks 
docs.docker.com

Multiple compose files & when not to rely on extends for list overrides 
docs.docker.com
docs.docker.com

Streamlit runOnSave for instant reloads in local dev 
docs.streamlit.io

You’re set
Commit this README to kiosk-llm-dev/, and the next maintainer can duplicate or debug the environment with a single glance.
