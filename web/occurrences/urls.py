"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `slowwalkerweb/urls.py` 가 붙인다."""
from django.urls import path

from . import views

app_name = "occurrences"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("occurrences.geojson", views.occurrences_geojson, name="geojson"),
    path("map-data.geojson", views.map_data, name="map_data"),
    path("sites/new/", views.SiteCreate.as_view(), name="site_create"),
    path("sites/<int:pk>/", views.SiteDetail.as_view(), name="site_detail"),
    path("sites/<int:pk>/edit/", views.SiteUpdate.as_view(), name="site_update"),
    path("sites/<int:pk>/data/", views.site_data, name="site_data"),
    path("events/new/", views.EventCreate.as_view(), name="event_create"),
    path("events/<int:pk>/", views.EventDetail.as_view(), name="event_detail"),
    path("events/<int:pk>/edit/", views.EventUpdate.as_view(), name="event_update"),
    path("samples/new/", views.SampleCreate.as_view(), name="sample_create"),
    path("samples/<int:pk>/", views.SampleDetail.as_view(), name="sample_detail"),
    path("samples/<int:pk>/edit/", views.SampleUpdate.as_view(), name="sample_update"),
    path("occurrences/", views.OccurrenceList.as_view(), name="list"),
    path("occurrences/new/", views.OccurrenceCreate.as_view(), name="create"),
    path("occurrences/<int:pk>/", views.OccurrenceDetail.as_view(), name="detail"),
    path("occurrences/<int:pk>/data/", views.occurrence_data, name="occurrence_data"),
    path("occurrences/<int:pk>/edit/", views.OccurrenceUpdate.as_view(), name="update"),
    path("occurrences/<int:pk>/delete/", views.OccurrenceDelete.as_view(), name="delete"),
    path("taxa/new/", views.TaxonCreate.as_view(), name="taxon_create"),
    path("healthz/", views.healthz, name="healthz"),
]
