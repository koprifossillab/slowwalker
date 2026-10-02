"""관리 화면. 산출은 전용 화면(`/occurrences/`)에서 넣고 고친다 — 여기는 분류군을 넣고 계정을 다루는 곳이다."""
from django.contrib import admin

from .models import Occurrence, Photo, Taxon


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    list_display = ("scientific_name", "authorship", "rank", "parent")
    list_filter = ("rank",)
    search_fields = ("scientific_name",)
    autocomplete_fields = ("parent",)


class PhotoInline(admin.TabularInline):
    model = Photo
    fields = ("image", "description", "creator", "license")
    extra = 0


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    inlines = [PhotoInline]
    list_display = ("taxon", "decimal_latitude", "decimal_longitude", "country", "locality",
                    "event_date", "basis_of_record")
    list_filter = ("basis_of_record", "country")
    search_fields = ("taxon__scientific_name", "locality", "country", "reference")
    autocomplete_fields = ("taxon",)
    date_hierarchy = "event_date"
    fieldsets = (
        (None, {"fields": ("taxon", "basis_of_record")}),
        ("자리", {"fields": (("decimal_latitude", "decimal_longitude"), "coordinate_uncertainty_m",
                            "country", "locality", "habitat", "elevation_m")}),
        ("채집", {"fields": ("event_date", "recorded_by")}),
        ("출처", {"fields": ("reference", "remarks")}),
    )
