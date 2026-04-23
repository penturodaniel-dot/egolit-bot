FROM python:3.11-slim

WORKDIR /app

# ── Install Node.js 20 for React build ────────────────────────────────────
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (cached layer) ───────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Node dependencies (cached layer — only re-runs if package.json changes)
COPY admin-react/package.json admin-react/package-lock.json* ./admin-react/
RUN cd admin-react && npm install --silent

# ── Copy all project code ─────────────────────────────────────────────────
COPY . .

# ── Build React app ────────────────────────────────────────────────────────
RUN cd admin-react && npm run build

# ── Runtime config ─────────────────────────────────────────────────────────
ENV PYTHONPATH=/app
RUN chmod +x start.sh

# Запускаємо бота + адмінку разом
CMD ["sh", "start.sh"]
