"""URL 뿌리.

서브패스(`SLOWWALKER_URL_PREFIX`)를 여기 한 곳에서만 붙인다. 앱의 `occurrences/urls.py` 는
접두사를 모른다 — nginx 가 어디에 걸든 앱은 그대로 돌아야 한다 (GSM 과 같다).
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

prefix = settings.URL_PREFIX

urlpatterns = [
    path(prefix, include("occurrences.urls")),
    path(f"{prefix}admin/", admin.site.urls),
]
