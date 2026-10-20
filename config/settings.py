import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.getenv("DJANGO_SECRET_KEY","unsafe-local-demo-key-change-me")
DEBUG=os.getenv("DJANGO_DEBUG","1").lower() in {"1","true","yes"}
ALLOWED_HOSTS=[h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS","localhost,127.0.0.1").split(",") if h.strip()]
INSTALLED_APPS=["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","analytics.apps.AnalyticsConfig"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware","whitenoise.middleware.WhiteNoiseMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/"templates"],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION="config.wsgi.application"
if os.getenv("POSTGRES_HOST"):
 DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":os.getenv("POSTGRES_DB","alfa_news"),"USER":os.getenv("POSTGRES_USER","alfa_news"),"PASSWORD":os.getenv("POSTGRES_PASSWORD","local_dev_password"),"HOST":os.getenv("POSTGRES_HOST","db"),"PORT":os.getenv("POSTGRES_PORT","5432"),"CONN_MAX_AGE":60,"OPTIONS":{"connect_timeout":5}}}
else: DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS=[]
LANGUAGE_CODE="ru-ru"; TIME_ZONE="Europe/Moscow"; USE_I18N=True; USE_TZ=True
STATIC_URL="static/"; STATIC_ROOT=BASE_DIR/"staticfiles"; STATICFILES_DIRS=[BASE_DIR/"static"]
STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"whitenoise.storage.CompressedManifestStaticFilesStorage"}}
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
SECURE_CONTENT_TYPE_NOSNIFF=True; X_FRAME_OPTIONS="DENY"; SESSION_COOKIE_HTTPONLY=True; SECURE_REFERRER_POLICY="same-origin"
if not DEBUG:
 SECURE_SSL_REDIRECT=os.getenv("SECURE_SSL_REDIRECT","1").lower() in {"1","true","yes"}
 SESSION_COOKIE_SECURE=True; CSRF_COOKIE_SECURE=True; SECURE_HSTS_SECONDS=int(os.getenv("SECURE_HSTS_SECONDS","31536000")); SECURE_HSTS_INCLUDE_SUBDOMAINS=True; SECURE_HSTS_PRELOAD=True
RSS_FEEDS=[x.strip() for x in os.getenv("RSS_FEEDS","").split(",") if x.strip()]
LLM_API_BASE_URL=os.getenv("LLM_API_BASE_URL","").strip(); LLM_API_KEY=os.getenv("LLM_API_KEY","").strip(); LLM_MODEL=os.getenv("LLM_MODEL","").strip(); LLM_TIMEOUT_SECONDS=int(os.getenv("LLM_TIMEOUT_SECONDS","35"))
