FROM python:3.11-slim

WORKDIR /app

# Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (includes pre-built admin-react/dist/)
COPY . .

ENV PYTHONPATH=/app
RUN chmod +x start.sh

# Run bot + admin together
CMD ["sh", "start.sh"]
