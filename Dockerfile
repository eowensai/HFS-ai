FROM python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

# Preserve the process-inspection policy with Python 3.14's debugger interface.
ENV PYTHON_DISABLE_REMOTE_DEBUG=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# --- OS packages --------------------------------------------------
RUN apt-get update \
 && apt-get install -y curl \
 && rm -rf /var/lib/apt/lists/*

# --- Python deps --------------------------------------------------
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock \
 && pip check

# --- Application code --------------------------------------------
COPY . .
# Server protections and theme are versioned together in .streamlit/config.toml.

EXPOSE 8501

CMD ["streamlit", "run", "ephemeral_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
