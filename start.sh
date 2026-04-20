#!/bin/sh
# Запускаємо бота і адмінку паралельно
python bot/main.py &
uvicorn admin.main:app --host 0.0.0.0 --port 8000
