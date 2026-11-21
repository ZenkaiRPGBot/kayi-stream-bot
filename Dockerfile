FROM python:3.11-slim

# Install system runtime tools: ffmpeg, ffprobe, gcc compiler
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    libffi-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure cache directories exist
RUN mkdir -p media_cache static

# Hugging Face Spaces standard port
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# Launch streaming engine
CMD ["python", "-u", "bot.py"]
