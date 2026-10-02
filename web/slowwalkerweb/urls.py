"""URL 뿌리.

서브패스(`SLOWWALKER_URL_PREFIX`)를 여기 한 곳에서만 붙인다. 앱의 `occurrences/urls.py` 는
접두사를 모른다 — nginx 가 어디에 걸든 앱은 그대로 돌아야 한다 (GSM 과 같다).
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve


def media(request, path):
    """`MEDIA_ROOT` 를 부를 때마다 읽는다 — 시험이 `override_settings` 로 바꾼 곳도 따라간다."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


prefix = settings.URL_PREFIX

urlpatterns = [
    path(prefix, include("occurrences.urls")),
    path(f"{prefix}admin/", admin.site.urls),
    path(f"{prefix}login/", auth_views.LoginView.as_view(template_name="occurrences/login.html"), name="login"),
    path(f"{prefix}logout/", auth_views.LogoutView.as_view(), name="logout"),
    # 올린 사진. DEBUG 와 상관없이 Django 가 내준다 — 아직 앞에 nginx 가 없다.
    # 배포(Docker)를 세울 때 nginx 가 `MEDIA_ROOT` 를 곧장 내주게 하고 이 줄을 뺀다
    re_path(rf"^{prefix}media/(?P<path>.*)$", media),
]
