FROM python:3.11-slim

WORKDIR /app

# Залежності окремим шаром — кешується при rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код проекту
COPY . .

CMD ["python", "bot/main.py"]
