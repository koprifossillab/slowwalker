"""반복 채집의 연결과 기존 기록 보존, 사진 소유권, 입력 권한을 검증한다."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from occurrences.forms import OccurrenceForm, SampleForm, SiteForm
from occurrences.models import CollectionEvent, Occurrence, Photo, Sample, Site, Taxon


def photo_file(name="sampling.png"):
    output = BytesIO()
    Image.new("RGB", (16, 16), (60, 90, 100)).save(output, "PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def site_form_data(**extra):
    return {"name": "검토용 해안", "decimal_latitude": "37.5", "decimal_longitude": "129.1",
            "realm": "marine", "locality": "조간대", "country": "대한민국", **extra}


def empty_photos():
    return {"photos-TOTAL_FORMS": 0, "photos-INITIAL_FORMS": 0,
            "photos-MIN_NUM_FORMS": 0, "photos-MAX_NUM_FORMS": 1000}


class Sampling(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.taxon = Taxon.objects.create(scientific_name="검토용 분류군 A")
        cls.site = Site.objects.create(name="반복 채집 해안", locality="조간대",
            decimal_latitude="37.5", decimal_longitude="129.1", realm=Site.Realm.MARINE)
        cls.event = CollectionEvent.objects.create(site=cls.site, event_date=date(2026, 5, 1),
            recorded_by="채집자 A", reference="채집 문헌")
        cls.sample = Sample.objects.create(event=cls.event, sample_code="B-01", substrate="따개비")
        cls.linked = Occurrence.objects.create(sample=cls.sample, taxon=cls.taxon,
            individual_count=3, identified_by="동정자 A", reference="산출 문헌")
        cls.legacy = Occurrence.objects.create(taxon=cls.taxon, decimal_latitude="37.5",
            decimal_longitude="129.1", locality="기존 독립 기록", reference="기존 문헌", elevation_m=123,
            coordinate_uncertainty_m=0)

    def test_반복_채집은_한_채집지에_묶고_기존_산출은_따로_남긴다(self):
        event2 = CollectionEvent.objects.create(site=self.site, event_date_verbatim="2026년 여름")
        sample2 = Sample.objects.create(event=event2, sample_code="B-01")
        Occurrence.objects.create(sample=sample2, taxon=self.taxon)
        data = self.client.get(reverse("occurrences:map_data")).json()
        self.assertEqual(len(data["features"]), 2)
        by_id = {feature["id"]: feature for feature in data["features"]}
        site = by_id[f"site:{self.site.pk}"]
        self.assertEqual(site["geometry"]["coordinates"], [129.1, 37.5])
        self.assertEqual(site["properties"]["event_count"], 2)
        self.assertEqual(site["properties"]["sample_count"], 2)
        self.assertEqual(site["properties"]["occurrence_count"], 2)
        self.assertEqual(site["properties"]["taxa"], [self.taxon.scientific_name])
        self.assertIn(f"occurrence:{self.legacy.pk}", by_id)
        nested = self.client.get(site["properties"]["data_url"]).json()
        self.assertEqual(len(nested["events"]), 2)
        uncertain = next(e for e in nested["events"] if e["id"] == event2.pk)
        self.assertIsNone(uncertain["event_date"])
        self.assertEqual(uncertain["event_date_verbatim"], "2026년 여름")
        for e in nested["events"]:
            self.assertIn(f"?event={e['id']}", e["sample_create_url"])

    def test_채집지_좌표와_채집정보를_고치면_연결산출도_새_정보를_보인다(self):
        Site.objects.filter(pk=self.site.pk).update(decimal_latitude="38.250000", locality="수정 산지")
        CollectionEvent.objects.filter(pk=self.event.pk).update(recorded_by="새 채집자")
        self.linked.refresh_from_db()
        self.assertIsNone(self.linked.decimal_latitude)
        features = self.client.get(reverse("occurrences:geojson")).json()["features"]
        linked = next(f for f in features if f["id"] == self.linked.pk)
        self.assertEqual(linked["geometry"]["coordinates"], [129.1, 38.25])
        self.assertEqual(linked["properties"]["coordinate_source"], "site")
        detail = self.client.get(reverse("occurrences:detail", args=[self.linked.pk]))
        self.assertContains(detail, 'data-lat="38.250000"')
        self.assertContains(detail, "새 채집자")
        self.assertContains(detail, "산출 문헌")
        self.assertContains(detail, "채집 문헌")
        listing = self.client.get(reverse("occurrences:list"), {"q": "수정 산지"})
        self.assertEqual([o.pk for o in listing.context["object_list"]], [self.linked.pk])
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.decimal_latitude, Decimal("37.5"))

    def test_시료에_연결해도_기존_단독_기록의_원문을_덮어쓰지_않는다(self):
        form = OccurrenceForm({"sample": self.sample.pk, "taxon": self.taxon.pk,
            "basis_of_record": "MaterialCitation", "reference": "기존 문헌"}, instance=self.legacy)
        self.assertTrue(form.is_valid(), form.errors)
        linked = form.save()
        self.assertEqual(linked.locality, "기존 독립 기록")
        self.assertEqual(linked.decimal_latitude, Decimal("37.5"))
        self.assertEqual(linked.effective_locality, "조간대")
        self.assertEqual(linked.reference, "기존 문헌")
        self.assertEqual(linked.elevation_m, 123)
        self.assertEqual(linked.coordinate_uncertainty_m, 0)

    def test_산출문헌은_채집문헌과_독립적으로_보존한다(self):
        self.assertEqual(self.linked.effective_reference, "산출 문헌")
        detail = self.client.get(reverse("occurrences:occurrence_data", args=[self.linked.pk])).json()
        self.assertEqual(detail["reference"], "산출 문헌")
        nested = self.client.get(reverse("occurrences:site_data", args=[self.site.pk])).json()
        self.assertEqual(nested["events"][0]["reference"], "채집 문헌")
        self.assertEqual(nested["events"][0]["samples"][0]["occurrences"][0]["reference"], "산출 문헌")
        self.linked.reference = ""
        self.assertEqual(self.linked.effective_reference, "채집 문헌")

    def test_좌표와_개체수_검사(self):
        for latitude, longitude in (("91", "0"), ("0", "181"), ("NaN", "0"), ("", "")):
            form = SiteForm(site_form_data(decimal_latitude=latitude, decimal_longitude=longitude))
            self.assertFalse(form.is_valid())
        for count in ("0", "-1"):
            form = OccurrenceForm({"sample": self.sample.pk, "taxon": self.taxon.pk,
                                  "basis_of_record": "PreservedSpecimen", "individual_count": count})
            self.assertFalse(form.is_valid())
            self.assertIn("individual_count", form.errors)
        form = OccurrenceForm({"taxon": self.taxon.pk, "basis_of_record": "PreservedSpecimen"})
        self.assertFalse(form.is_valid())
        self.assertIn("decimal_latitude", form.errors)
        form = OccurrenceForm({"taxon": self.taxon.pk, "basis_of_record": "PreservedSpecimen",
            "decimal_latitude": "1", "decimal_longitude": "2", "coordinate_uncertainty_m": "0"})
        self.assertFalse(form.is_valid())
        self.assertIn("coordinate_uncertainty_m", form.errors)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Occurrence.objects.create(taxon=self.taxon)

    def test_지도_좌표와_부모_선택을_미리_채운다(self):
        form = self.client.get(reverse("occurrences:site_create"), {"lat": "0", "lon": "180"}).context["form"]
        self.assertEqual(form.initial["decimal_latitude"], Decimal("0"))
        self.assertEqual(form.initial["decimal_longitude"], Decimal("180"))
        form = self.client.get(reverse("occurrences:site_create"), {"lat": "Infinity", "lon": "181"}).context["form"]
        self.assertNotIn("decimal_latitude", form.initial)
        self.assertNotIn("decimal_longitude", form.initial)
        for route, key, obj in (("event_create", "site", self.site), ("sample_create", "event", self.event),
                                 ("create", "sample", self.sample)):
            form = self.client.get(reverse(f"occurrences:{route}"), {key: obj.pk}).context["form"]
            self.assertEqual(form.initial[key], obj.pk)

    def test_채집_시료_산출_입력을_이어간다(self):
        response = self.client.post(reverse("occurrences:site_create"), site_form_data())
        site = Site.objects.get(name="검토용 해안")
        self.assertRedirects(response, reverse("occurrences:site_detail", args=[site.pk]))
        response = self.client.post(reverse("occurrences:event_create"), {
            "site": site.pk, "event_date": "", "event_date_verbatim": "2025년 5~6월", "recorded_by": "학생 A"})
        event = site.events.get()
        self.assertRedirects(response, reverse("occurrences:event_detail", args=[event.pk]))
        response = self.client.post(reverse("occurrences:sample_create"), {
            "event": event.pk, "sample_code": "B-02", "substrate": "따개비", "host_taxon": "Balanus sp."})
        sample = event.samples.get()
        self.assertRedirects(response, reverse("occurrences:sample_detail", args=[sample.pk]))
        response = self.client.post(reverse("occurrences:create"), {"sample": sample.pk,
            "taxon": self.taxon.pk, "basis_of_record": "PreservedSpecimen", "individual_count": "2"})
        occ = sample.occurrences.get()
        self.assertRedirects(response, reverse("occurrences:detail", args=[occ.pk]))
        self.assertIsNone(occ.decimal_latitude)
        self.assertEqual(occ.effective_recorded_by, "학생 A")
        self.assertEqual(occ.individual_count, 2)
        form = SampleForm({"event": event.pk, "sample_code": "B-02"})
        self.assertFalse(form.is_valid())

    def test_새_분류군을_넣고_돌아와도_선택한_시료를_유지한다(self):
        response = self.client.post(reverse("occurrences:taxon_create"), {
            "scientific_name": "검토용 분류군 B", "rank": "species",
            "next": f"{reverse('occurrences:create')}?sample={self.sample.pk}"})
        self.assertIn(f"sample={self.sample.pk}", response.url)
        self.assertIn("taxon=", response.url)

    @override_settings(EDIT_REQUIRES_LOGIN=True)
    def test_새_입력과_수정에도_로그인이_필요하다(self):
        for route, args in (("site_create", []), ("site_update", [self.site.pk]),
            ("event_create", []), ("event_update", [self.event.pk]),
            ("sample_create", []), ("sample_update", [self.sample.pk])):
            response = self.client.get(reverse(f"occurrences:{route}", args=args))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)
        self.client.force_login(User.objects.create_user("sampling-editor"))
        self.assertEqual(self.client.get(reverse("occurrences:site_create")).status_code, 200)
        for route, args in (("site_detail", [self.site.pk]), ("site_data", [self.site.pk]), ("map_data", [])):
            self.assertEqual(Client().get(reverse(f"occurrences:{route}", args=args)).status_code, 200)

    def test_새_입력도_CSRF를_검사한다(self):
        response = Client(enforce_csrf_checks=True).post(reverse("occurrences:site_create"), site_form_data())
        self.assertEqual(response.status_code, 403)


class SamplingPhotos(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory(prefix="slowwalker-sampling-test-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.settings_override.disable)
        self.site = Site.objects.create(name="사진 채집지", decimal_latitude=1, decimal_longitude=2)
        self.event = CollectionEvent.objects.create(site=self.site)
        self.sample = Sample.objects.create(event=self.event, sample_code="P-1")
        self.taxon = Taxon.objects.create(scientific_name="사진 검토 분류군")

    def test_채집지_시료_사진을_따로_붙이고_수정하며_삭제한다(self):
        response = self.client.post(reverse("occurrences:site_update", args=[self.site.pk]), {
            **site_form_data(name=self.site.name), **empty_photos(), "new_photos": [photo_file()]})
        self.assertEqual(response.status_code, 302)
        site_photo = self.site.photos.get()
        self.assertTrue(site_photo.image.name.startswith(f"photos/sites/{self.site.pk}/"))
        response = self.client.post(reverse("occurrences:sample_update", args=[self.sample.pk]), {
            "event": self.event.pk, "sample_code": self.sample.sample_code,
            **empty_photos(), "new_photos": [photo_file()]})
        self.assertEqual(response.status_code, 302)
        sample_photo = self.sample.photos.get()
        self.assertTrue(sample_photo.image.name.startswith(f"photos/samples/{self.sample.pk}/"))
        data = self.client.get(reverse("occurrences:site_data", args=[self.site.pk])).json()
        self.assertEqual(data["photos"][0]["url"], site_photo.image.url)
        self.assertEqual(data["events"][0]["samples"][0]["photos"][0]["url"], sample_photo.image.url)
        image_name, thumbnail_name, storage = sample_photo.image.name, sample_photo.thumbnail.name, sample_photo.image.storage
        response = self.client.post(reverse("occurrences:sample_update", args=[self.sample.pk]), {
            "event": self.event.pk, "sample_code": self.sample.sample_code,
            "photos-TOTAL_FORMS": 1, "photos-INITIAL_FORMS": 1,
            "photos-0-id": sample_photo.pk, "photos-0-sample": self.sample.pk, "photos-0-DELETE": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.sample.photos.exists())
        self.assertFalse(storage.exists(image_name))
        self.assertFalse(storage.exists(thumbnail_name))
        self.assertTrue(self.site.photos.exists())

    def test_사진은_정확히_한_소유자만_받는다(self):
        for kwargs in ({}, {"site": self.site, "sample": self.sample}):
            with self.assertRaises(ValidationError):
                Photo(**kwargs).clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                Photo.objects.bulk_create([Photo(image="not-written.jpg", **kwargs)])

    def test_다른_학생이_사진을_먼저_지워도_오류_페이지가_아닌_양식을_보인다(self):
        response = self.client.post(reverse("occurrences:site_update", args=[self.site.pk]), {
            **site_form_data(name=self.site.name), "photos-TOTAL_FORMS": 1, "photos-INITIAL_FORMS": 1,
            "photos-0-id": 999999, "photos-0-site": self.site.pk, "photos-0-description": "수정 설명"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["photo_formset"].errors[0]["id"])

    def test_관리화면은_아직_저장하지_않은_부모의_사진도_검사한다(self):
        for model, parent in ((Site, Site(name="새 채집지", decimal_latitude=0, decimal_longitude=0)),
            (Sample, Sample(event=self.event, sample_code="새 시료")),
            (Occurrence, Occurrence(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0))):
            formset_type = forms.inlineformset_factory(model, Photo, fields=["image", "description"], extra=0)
            formset = formset_type({"photos-TOTAL_FORMS": 1, "photos-INITIAL_FORMS": 0},
                {"photos-0-image": photo_file()}, instance=parent)
            self.assertTrue(formset.is_valid(), (model, formset.errors))
