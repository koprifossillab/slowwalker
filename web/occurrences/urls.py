"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `slowwalkerweb/urls.py` 가 붙인다."""
from django.urls import path

from . import views

app_name = "occurrences"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("occurrences.geojson", views.occurrences_geojson, name="geojson"),
    path("occurrences/", views.OccurrenceList.as_view(), name="list"),
    path("occurrences/new/", views.OccurrenceCreate.as_view(), name="create"),
    path("occurrences/<int:pk>/", views.OccurrenceDetail.as_view(), name="detail"),
    path("occurrences/<int:pk>/edit/", views.OccurrenceUpdate.as_view(), name="update"),
    path("occurrences/<int:pk>/delete/", views.OccurrenceDelete.as_view(), name="delete"),
    path("taxa/new/", views.TaxonCreate.as_view(), name="taxon_create"),
    path("healthz/", views.healthz, name="healthz"),
]
