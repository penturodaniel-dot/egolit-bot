FROM python:3.11-slim

WORKDIR /app

# Залежності окремим шаром — кешується при rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код проекту
COPY . .

# PYTHONPATH щоб всі модулі (config, db, ai) знаходились відносно /app
ENV PYTHONPATH=/app

RUN chmod +x start.sh

# Запускаємо бота + адмінку разом
CMD ["sh", "start.sh"]
