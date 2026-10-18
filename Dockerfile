FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app app
COPY data data
COPY scripts scripts
RUN useradd --create-home cci && mkdir -p /app/work /app/data/index && chown -R cci:cci /app
RUN mkdir -p /home/cci/.ssh && chown cci:cci /home/cci/.ssh && chmod 0700 /home/cci/.ssh
USER cci
ENV HF_HOME=/app/work/huggingface HF_HUB_DISABLE_XET=1 TIKTOKEN_CACHE_DIR=/app/work/tiktoken
EXPOSE 8000
CMD ["python", "scripts/serve.py"]
