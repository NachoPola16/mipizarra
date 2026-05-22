FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=mipizarra_cfg.settings
RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["gunicorn", "mipizarra_cfg.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "320"]
