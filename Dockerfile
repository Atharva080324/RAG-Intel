FROM python:3.12-slim

WORKDIR /usr/src/app

# Tesseract enables the OCR fallback; supervisor keeps both the FastAPI server
# and the Celery worker alive inside this single HF Spaces container.
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr supervisor && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN chmod +x start.sh

# Hugging Face Spaces uses port 7860; Railway / Render set $PORT at runtime.
# The entrypoint scripts read $PORT so the same image works everywhere.
EXPOSE 7860 8000

ENV HF_HOME=/tmp/huggingface \
    PORT=7860

CMD ["sh", "start.sh"]
