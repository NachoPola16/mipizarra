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
# jugadas.json is the private play library: the login-protected view in pizarra/cuentas.py reads it from the app
# directory, so it must NOT be collected into STATIC_ROOT (WhiteNoise would serve it to anyone, no login).
RUN python manage.py collectstatic --no-input --ignore jugadas.json

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --no-input && exec gunicorn mipizarra_cfg.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 700"]
