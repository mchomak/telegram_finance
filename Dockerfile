FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install torch before copying requirements.txt so this heavy layer is cached
# independently — changes to requirements.txt won't trigger a torch reinstall.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Pre-download Whisper model at build time as botuser to avoid runtime permission issues
# with the named volume — volume is initialized from the image directory on first mount.
ARG WHISPER_MODEL=base
RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')"

CMD ["python", "-m", "bot.main"]
