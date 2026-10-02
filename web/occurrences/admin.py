"""산출 기록은 지금은 Django 관리 화면에서 넣고 고친다. 전용 입력 화면은 필요해지면 만든다."""
from django.contrib import admin

from .models import Occurrence, Taxon


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    list_display = ("scientific_name", "authorship", "rank", "parent")
    list_filter = ("rank",)
    search_fields = ("scientific_name",)
    autocomplete_fields = ("parent",)


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
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
