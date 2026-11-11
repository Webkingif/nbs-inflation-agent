FROM docker.n8n.io/n8nio/n8n:latest

# Switch to root to install packages
USER root

# Install Python 3, pip, and system build tools if needed
RUN apk add --no-cache python3 py3-pip python3-dev build-base

# Copy requirements.txt into the container
COPY requirements.txt /tmp/requirements.txt

# Install the Python packages globally inside the container
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Switch back to the standard n8n user for security
USER node