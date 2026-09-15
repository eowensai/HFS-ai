FROM python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS privacy
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY deployment/privacy/nodump.c /src/nodump.c
RUN cc -shared -fPIC -O2 -Wall -Wextra -Werror -o /libephemerai_nodump.so /src/nodump.c

FROM python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6
ENV PYTHON_DISABLE_REMOTE_DEBUG=1 PYTHONDONTWRITEBYTECODE=1 LD_PRELOAD=/opt/ephemerai/libephemerai_nodump.so
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock && pip check
COPY --from=privacy /libephemerai_nodump.so /opt/ephemerai/libephemerai_nodump.so
COPY ephemeral/ ./ephemeral/
COPY .streamlit/ ./.streamlit/
COPY static/ ./static/
COPY ephemeral_app.py theme.css system_prompt_template.md ./
EXPOSE 8501
CMD ["streamlit", "run", "ephemeral_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
