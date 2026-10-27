import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

def _clave_secreta():
    """DJANGO_SECRET_KEY si está en el entorno. Si no, una clave aleatoria generada UNA vez y guardada junto a la base
    de datos: los workers de gunicorn deben compartirla (la sesión de la cuenta se firma con ella) y no debe
    cambiar al reiniciar. Nunca queda una clave conocida en el repositorio."""
    del_entorno = os.environ.get('DJANGO_SECRET_KEY')
    if del_entorno:
        return del_entorno
    ruta = Path(os.environ.get('DJANGO_DB_PATH') or BASE_DIR / 'db.sqlite3').parent / 'secret_key.txt'
    try:
        if ruta.exists():
            return ruta.read_text(encoding='utf-8').strip()
        clave = get_random_secret_key()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(clave, encoding='utf-8')
        return clave
    except OSError:
        return get_random_secret_key()      # sin disco escribible: clave de este proceso (la sesión no sobrevive)


SECRET_KEY = _clave_secreta()
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost 127.0.0.1').split()

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'pizarra',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'mipizarra_cfg.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mipizarra_cfg.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
            ],
        },
    },
]

WSGI_APPLICATION = 'mipizarra_cfg.wsgi.application'

# Base de datos de las cuentas (jugadas guardadas). En Docker vive en un volumen (/data) para que sobreviva a los
# contenedores; en local, junto al código.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH') or str(BASE_DIR / 'db.sqlite3'),
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Las cuentas las crea el administrador con `manage.py createsuperuser`; no hay registro público.
LOGIN_URL = '/cuenta/entrar/'
LOGIN_REDIRECT_URL = '/jugadas/'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
# Detrás de HTTPS (dominio con proxy) conviene DJANGO_COOKIE_SECURE=True; por HTTP en la LAN debe quedar en False
# o el navegador descarta la cookie y no se puede iniciar sesión.
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = os.environ.get('DJANGO_COOKIE_SECURE', 'False') == 'True'
# Orígenes permitidos para los formularios por HTTPS detrás del proxy (p. ej. https://mipizarra.polacabezon.com).
CSRF_TRUSTED_ORIGINS = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split()

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.ManifestStaticFilesStorage'

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

API_URL         = os.environ.get('API_URL', 'http://mipizarra-api:8090')
INTERNAL_SECRET = os.environ.get('INTERNAL_SECRET', '')
