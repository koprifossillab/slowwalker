"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `slowwalkerweb/urls.py` 가 붙인다."""
from django.urls import path

from . import views

app_name = "occurrences"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("occurrences.geojson", views.occurrences_geojson, name="geojson"),
    path("healthz/", views.healthz, name="healthz"),
]
