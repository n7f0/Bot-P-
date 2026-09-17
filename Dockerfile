FROM python:3.11-slim

# Variáveis de ambiente para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependências do sistema (necessárias para discord.py[voice] / PyNaCl)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libnacl-dev \
        libsodium-dev \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python primeiro (melhor cache de camadas)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia o código do bot
COPY bot.py .
COPY database.py .

# Cria o diretório de dados persistentes
RUN mkdir -p /app/data

# Usuário não-root (segurança)
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Comando de inicialização
CMD ["python", "-u", "bot.py"]
