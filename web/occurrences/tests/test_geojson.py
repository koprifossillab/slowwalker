"""산출이 GeoJSON 으로 나가는 꼴. 지도가 기대는 것은 이것 하나다."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from occurrences.models import Occurrence, Taxon


class Geojson(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.milnesium = Taxon.objects.create(scientific_name="Milnesium tardigradum",
                                             authorship="Doyère, 1840")
        cls.echiniscus = Taxon.objects.create(scientific_name="Echiniscus testudo")
        Occurrence.objects.create(taxon=cls.milnesium, decimal_latitude="-62.223000",
                                  decimal_longitude="-58.786000", country="Antarctica",
                                  locality="King Sejong Station", event_date=date(2025, 1, 15))
        Occurrence.objects.create(taxon=cls.echiniscus, decimal_latitude="37.5665",
                                  decimal_longitude="126.978")

    def test_좌표는_경도가_앞에_온다(self):
        res = self.client.get(reverse("occurrences:geojson"))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["type"], "FeatureCollection")
        sejong = next(f for f in data["features"] if f["properties"]["locality"] == "King Sejong Station")
        self.assertEqual(sejong["geometry"]["coordinates"], [-58.786, -62.223])
        self.assertEqual(sejong["properties"]["event_date"], "2025-01-15")

    def test_분류군으로_거른다(self):
        res = self.client.get(reverse("occurrences:geojson"), {"taxon": self.echiniscus.pk})
        names = [f["properties"]["taxon"] for f in res.json()["features"]]
        self.assertEqual(names, ["Echiniscus testudo"])

    def test_분류군이_숫자가_아니면_400(self):
        res = self.client.get(reverse("occurrences:geojson"), {"taxon": "x"})
        self.assertEqual(res.status_code, 400)


class Pages(TestCase):
    def test_지도가_뜬다(self):
        res = self.client.get(reverse("occurrences:map"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "occurrences/vendor/ol.js")

    def test_healthz(self):
        res = self.client.get(reverse("occurrences:healthz"))
        self.assertEqual(res.json()["status"], "ok")
