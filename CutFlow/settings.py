from pathlib import Path
import os
from decouple import RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file into os.environ
env_file = BASE_DIR / '.env'
if env_file.exists():
    try:
        env_config = RepositoryEnv(env_file)
        for key, value in env_config.data.items():
            os.environ.setdefault(key, value)
    except Exception:
        pass

SECRET_KEY = os.environ.get('SECRET_KEY', 'cutflow-dev-secret-key-change-in-production-2026')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Internal apps
    'accounts',
    'catalog',
    'projects',
    'quotations',
    'production',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.RoleMiddleware',
]

ROOT_URLCONF = 'CutFlow.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.company_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'CutFlow.wsgi.application'

USE_SQLITE = os.environ.get('USE_SQLITE', 'False') == 'True' or not os.environ.get('DB_NAME')

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'cutflow_db'),
            'USER': os.environ.get('DB_USER', 'cutflow_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
    if not os.environ.get('DB_PASSWORD'):
        import warnings
        warnings.warn(
            'DB_PASSWORD is not set in the environment/.env file. '
            'Set USE_SQLITE=True for local development, or provide DB_PASSWORD for MySQL.',
            RuntimeWarning,
        )

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = []   # No project-level static files; all assets loaded from CDN in base.html
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Email
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@cutflow.com')

# Company defaults (overridden via DB CompanySettings)
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'CutFlow Fenestration')
COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS', '')
COMPANY_PHONE = os.environ.get('COMPANY_PHONE', '')
COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL', '')

# Optimization defaults
DEFAULT_BAR_LENGTH_MM = 6000
DEFAULT_KERF_MM = 5
DEFAULT_END_WASTE_MM = 10
MIN_REUSABLE_OFFCUT_MM = 300
