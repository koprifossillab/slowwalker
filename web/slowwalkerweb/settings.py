"""slowwalker Django 설정.

환경변수는 전부 `SLOWWALKER_*` 이고 저장소 뿌리의 `.env` 에서 온다. GSM 의
`gsmweb/settings.py` 를 본떴다 — python-dotenv 를 쓰지 않고 `_load_env()` 열 줄로 읽는다.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent   # web/
REPO_DIR = BASE_DIR.parent                          # 저장소 뿌리


def _load_env(path: Path) -> None:
    """`.env` 를 환경변수로 올린다. 이미 있는 값은 덮지 않는다 —
    컨테이너가 넘겨준 것이 파일보다 세다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env(REPO_DIR / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def env_int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


SECRET_KEY = env("SLOWWALKER_SECRET_KEY", "개발용-바꿔야-한다")
DEBUG = env_bool("SLOWWALKER_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("SLOWWALKER_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("SLOWWALKER_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# 서브패스. 비우면 뿌리(`/`)에 선다. 붙이는 곳은 `slowwalkerweb/urls.py` 한 곳뿐이다.
URL_PREFIX = env("SLOWWALKER_URL_PREFIX", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "occurrences",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # DEBUG=0 이면 Django 가 정적 파일을 안 내준다. OpenLayers 를 파일로 부르므로
    # 없으면 화면은 뜨되 지도가 안 그려진다 (GSM requirements-web.txt 의 주석).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "slowwalkerweb.urls"
WSGI_APPLICATION = "slowwalkerweb.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "occurrences.context_processors.site",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("SLOWWALKER_DB_PATH", str(REPO_DIR / "slowwalker.db")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{n}"} for n in (
        "UserAttributeSimilarityValidator", "MinimumLengthValidator",
        "CommonPasswordValidator", "NumericPasswordValidator")
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"/{URL_PREFIX}static/" if URL_PREFIX else "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# 올린 사진. 저장소 안(web/media/, .gitignore 에 있다)이 기본이다
MEDIA_URL = f"/{URL_PREFIX}media/" if URL_PREFIX else "/media/"
MEDIA_ROOT = Path(env("SLOWWALKER_MEDIA_DIR", str(BASE_DIR / "media")))

# 사진 한 장의 크기 한계(MB). 현미경 원본 TIFF 도 대개 이 안에 든다
MAX_PHOTO_MB = env_int("SLOWWALKER_MAX_PHOTO_MB", 20)

# 산출을 넣기·고치기·지우기에 로그인을 묻는가. 연구소 안에서 시험하는 동안은 끈다(누구나 고친다).
# 밖에 열거나 기록이 쌓이면 1 로 켠다. 계정은 `createsuperuser` 나 관리 화면에서 만든다
EDIT_REQUIRES_LOGIN = env_bool("SLOWWALKER_EDIT_REQUIRES_LOGIN", False)

# 예시 자료가 든 별도 검토 화면에서만 표시한다. 연구 자료 화면의 기본값은 빈 글이다.
PREVIEW_NOTICE = env("SLOWWALKER_PREVIEW_NOTICE", "")

# 로그인 화면의 이름. 접두사(`URL_PREFIX`)는 urls.py 가 붙인다
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "occurrences:list"
LOGOUT_REDIRECT_URL = "occurrences:map"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("SLOWWALKER_LOG_LEVEL", "INFO")},
}
