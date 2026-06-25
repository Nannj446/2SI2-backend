#!/bin/bash
# Script de inicio para Railway
# Establece GUNICORN_WORKER_ID=1 para el primer worker

export GUNICORN_WORKER_ID=1
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
