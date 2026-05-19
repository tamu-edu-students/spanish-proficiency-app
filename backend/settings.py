from pathlib import Path
from dotenv import load_dotenv
import os
import dj_database_url

# Load .env file FIRST
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-1ni!34_it^fyk@a3gg6viaocnedni0$bhlyv-nh*p=_5q$u++7'

DEBUG = True

ALLOWED_HOSTS = ['*']

# ── Dev mode flag ─────────────────────────────────────────────
# True  = skip CAS, use local testing
# False = use real TAMU CAS login (production)
DEV_MODE = os.getenv('DEV_MODE', 'True') == 'True'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'django_cas_ng',  # CAS authentication
    'spanish',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_cas_ng.middleware.CASMiddleware',  # CAS middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'django_cas_ng.backends.CASBackend',  # CAS backend
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ── Database ──────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR}/db.sqlite3",
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Gemini API ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ── CORS ──────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
]
CORS_ALLOW_CREDENTIALS = True

# ── Session cookies ───────────────────────────────────────────
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True

# ── CAS Settings ─────────────────────────────────────────────
# TAMU CAS server URL
CAS_SERVER_URL        = 'https://cas.tamu.edu/cas/'

# Where to go after login/logout
CAS_REDIRECT_URL      = 'http://localhost:5173'
CAS_LOGOUT_COMPLETELY = True

# Automatically create Django user on first CAS login
CAS_AUTO_CREATE_USER  = True

# Get extra info from CAS (name, email)
CAS_APPLY_ATTRIBUTES_TO_USER = True
CAS_RENAME_ATTRIBUTES = {
    'firstName': 'first_name',
    'lastName':  'last_name',
    'email':     'email',
}

# ── Channels ──────────────────────────────────────────────────
ASGI_APPLICATION = 'backend.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# ── Cache ─────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND':  'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'espanol-ai-cache',
    }
}