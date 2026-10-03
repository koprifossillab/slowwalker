"""관리 화면. 산출은 전용 화면(`/occurrences/`)에서 넣고 고친다 — 여기는 분류군을 넣고 계정을 다루는 곳이다."""
from django.contrib import admin

from .models import CollectionEvent, Occurrence, Photo, Sample, Site, Taxon


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
    autocomplete_fields = ("taxon", "sample")
    date_hierarchy = "event_date"
    fieldsets = (
        (None, {"fields": ("taxon", "basis_of_record", "sample", "individual_count", "identified_by", "identification_qualifier")}),
        ("자리", {"fields": (("decimal_latitude", "decimal_longitude"), "coordinate_uncertainty_m",
                            "country", "locality", "habitat", "elevation_m")}),
        ("채집", {"fields": ("event_date", "recorded_by")}),
        ("출처", {"fields": ("reference", "remarks")}),
    )


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    inlines = [PhotoInline]
    list_display = ("name", "realm", "country", "decimal_latitude", "decimal_longitude")
    list_filter = ("realm", "country")
    search_fields = ("name", "locality", "country")


@admin.register(CollectionEvent)
class CollectionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "site", "event_date", "event_date_verbatim", "recorded_by")
    search_fields = ("site__name", "recorded_by", "reference")
    autocomplete_fields = ("site",)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    inlines = [PhotoInline]
    list_display = ("sample_code", "event", "substrate", "host_taxon")
    search_fields = ("sample_code", "event__site__name", "host_taxon")
    autocomplete_fields = ("event",)
