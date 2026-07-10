FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    REMOTION_BROWSER_EXECUTABLE=/usr/bin/chromium \
    OPENMONTAGE_CACHE_DIR=/workspace/cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        chromium \
        curl \
        ffmpeg \
        fonts-dejavu \
        fonts-liberation \
        git \
        make \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py ./
RUN pip install -r requirements.txt \
    && pip install piper-tts

COPY remotion-composer/package*.json ./remotion-composer/
RUN cd remotion-composer && npm ci

COPY . .
RUN python -m compileall lib tools schemas

VOLUME ["/workspace"]

CMD ["bash", "-lc", "python -c \"from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))\" && python tools/deploy/api_server.py"]
