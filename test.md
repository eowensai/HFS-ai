EphemerAl: A Self-Hosted, Private Web UI for Local LLMs
(https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)



A lightweight, Docker-based web interface for private, offline, and ephemeral conversations with your documents and images, powered by Google's Gemma 3 and Ollama.

!()
Consider replacing the static screenshot with an animated GIF to demonstrate the UI in action.

The Problem: Secure, Local AI without the Overhead
Are you looking for a complete solution to host a web-based AI service on your local network? Commercial cloud platforms come with recurring costs and data privacy risks, while many open-source alternatives are complex or built for features you don't need. EphemerAl was created to solve this problem: a simple, secure, and entirely self-hosted AI chat interface that prioritizes local data privacy and ease of deployment.

This project began as a personal effort to solve a problem at my workplace. I’m not a developer by trade, but I used AI tools to help bring it to life. While it wasn’t built for broad distribution, I’m sharing this generalized version in case it helps others looking for a secure, account-free, multimodal LLM interface for internal tools, training environments, or experimentation.

Key Features
🤖 Private AI Assistant: Real-time chat interface powered by Google’s state-of-the-art Gemma 3 model, served locally via Ollama.

📄 Retrieval-Augmented Generation (RAG): Upload 100+ file types through Apache Tika. The full text of your documents is injected directly into the conversation, allowing the AI to answer questions based on your private data.

🖼️ Multimodal Support: Analyze images alongside text queries using Gemma 3’s built-in vision capabilities.

🔒 Ephemeral & Secure by Design: No chat history or session data is ever stored. All processing runs on your local hardware, and no data ever leaves your network. No internet access is required after the initial setup.

🐳 Simple Docker Deployment: Get up and running quickly with a pre-configured Docker Compose setup. No prior Docker or WSL experience is required.

🎨 Customizable Interface: A clean, minimal UI with an optional logo or image block for lightweight internal branding.

Why EphemerAl?
While full-featured solutions like() are excellent for robust, multi-user environments, EphemerAl is designed for a different purpose. It is intentionally minimal, focusing on simplicity, privacy, and zero data persistence. It's the ideal choice for:

Internal Tools: Quickly spin up a secure Q&A tool for internal documentation.

Training Environments: Provide a safe, sandboxed environment for learning about LLMs.

Rapid Experimentation: Test local models and RAG concepts without the complexity of a larger platform.

Technical Stack
EphemerAl is a containerized web app designed to run fully offline after initial setup. It uses Docker Compose and Windows Subsystem for Linux 2 (WSL2) to create a clean, isolated environment on your existing Windows 11 system.

Host OS: Windows 11 Pro / Enterprise

Virtualization: Windows Subsystem for Linux 2 (WSL2) with Ubuntu 24.04

Containerization: Docker Engine

ephemeral-app: Streamlit-based user interface

ollama: Local LLM backend serving Google's Gemma 3

tika-server: Apache Tika for document parsing and text extraction

System Requirements & Setup
OS: Windows 11 Pro or Enterprise (fully updated)

GPU: At least one discrete NVIDIA GPU

30-series or newer is strongly recommended.

12GB+ VRAM is suggested for smooth performance with Gemma 3 12B.

Driver: Latest WHQL NVIDIA GPU driver.

Deployment is straightforward: Follow the step-by-step instructions in the included (System%20Deployment%20Guide.md). Most commands are ready to copy and paste directly into PowerShell.

Accessing the Interface
From the server: Visit http://localhost:8501

From another machine on your network: Visit http://<windows_host_ip_address>:8501

Community & Contributions
This project is shared as-is, and no official support is provided. However, community contributions, bug reports, and suggestions are welcome!

If you run into issues, the best approach is to:

Open a  to document the problem for the community.

For self-troubleshooting, try pasting the error message, a screenshot, and the relevant configuration files into an AI assistant for guidance. This often provides a helpful path to a solution.

Opportunities for Contribution (Known Issues)
The following are known limitations that would make great starting points for contributions:

The UI does not render correctly on mobile devices.

Minimizing the sidebar cannot be undone without a page refresh.

User text may draw under the input box arrow icon before wrapping correctly.

Attachments disappear visually after submission but remain in context for the model.

There is no guardrail for exceeding the model's context limit. Graceful error handling would be a valuable addition.

License
This project is licensed under the MIT License. See the(LICENSE) file for details.
