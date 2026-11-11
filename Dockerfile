FROM docker.n8n.io/n8nio/n8n:latest

USER root

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /tmp/requirements.txt

RUN if [ -f /tmp/requirements.txt ]; then \
    pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt; \
    fi

USER node