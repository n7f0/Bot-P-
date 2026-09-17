FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libnacl-dev \
        libsodium-dev \
        ffmpeg \
        ca-certificates \
        gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependências Python primeiro (cache de camadas)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Código
COPY bot.py .
COPY database.py .

# Entrypoint que corrige permissões do /app/data antes de rodar
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cria pasta de dados
RUN mkdir -p /app/data

# Cria usuário não-root
RUN useradd -m -u 1000 botuser

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-u", "bot.py"]
