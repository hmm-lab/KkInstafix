# Dockerfile for KkInstafix
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any)
# For example, if we need gcc or something, but we don't for now
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the rest of the application
COPY . .

# Expose port (if needed, but the bot doesn't expose a port by itself; it uses webhook or polling)
# EXPOSE 8080

# Set environment variables (optional, can be set at runtime)
# ENV BOT_TOKEN=

# Run the bot
CMD ["python", "bot.py"]