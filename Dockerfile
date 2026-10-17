FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY data data
COPY scripts scripts
RUN useradd --create-home cci && mkdir -p /app/work /app/data/index && chown -R cci:cci /app
USER cci
ENV HF_HOME=/app/work/huggingface HF_HUB_DISABLE_XET=1 TIKTOKEN_CACHE_DIR=/app/work/tiktoken
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
