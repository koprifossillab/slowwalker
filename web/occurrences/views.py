from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from slowwalkerweb.version import VERSION

from .models import Occurrence


def map_view(request):
    """세계지도. 점은 브라우저가 `occurrences.geojson` 에서 받아 그린다."""
    return render(request, "occurrences/map.html", {"version": VERSION})


def occurrences_geojson(request):
    """산출 전부를 GeoJSON FeatureCollection 으로.

    `?taxon=<id>` 로 분류군 하나만 거른다. 기록이 수만 개를 넘으면 범위(bbox)로 자르는
    것을 더한다 — 지금은 통째로 낸다.
    """
    qs = Occurrence.objects.select_related("taxon")
    taxon = request.GET.get("taxon")
    if taxon:
        if not taxon.isdigit():
            return JsonResponse({"error": "taxon 은 숫자여야 한다"}, status=400)
        qs = qs.filter(taxon_id=int(taxon))
    return JsonResponse({
        "type": "FeatureCollection",
        "features": [o.as_feature() for o in qs],
    })


def healthz(request):
    """판과 DB 를 본다. DB 를 못 열면 503."""
    info = {"status": "ok", "version": VERSION}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        info["occurrences"] = Occurrence.objects.count()
    except Exception as exc:  # DB 가 무엇으로 멈췄든 503 으로 알린다
        info.update(status="unhealthy", error=str(exc))
        return JsonResponse(info, status=503)
    return JsonResponse(info)
