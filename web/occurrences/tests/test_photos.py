"""산출 사진 — 올리기, 섬네일, 지도에 싣기, 빼기, 지울 때 파일까지."""
import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from occurrences.models import Occurrence, Photo, Taxon

MEDIA = tempfile.mkdtemp(prefix="slowwalker-test-media-")


def image_file(name="moss.png", size=(1200, 800), mode="RGB", fmt="PNG", color=(40, 120, 60)):
    buf = BytesIO()
    Image.new(mode, size, color).save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def form_data(taxon, **over):
    data = {"taxon": taxon.pk, "basis_of_record": "PreservedSpecimen",
            "decimal_latitude": "37.5", "decimal_longitude": "127.0"}
    data.update(over)
    return data


def formset_data(occ, rows=None):
    """고치기 화면의 사진 줄(management form 포함). rows 는 {사진 pk: {칸: 값}}."""
    photos = list(occ.photos.all())
    data = {"photos-TOTAL_FORMS": len(photos), "photos-INITIAL_FORMS": len(photos),
            "photos-MIN_NUM_FORMS": 0, "photos-MAX_NUM_FORMS": 1000}
    for i, ph in enumerate(photos):
        data[f"photos-{i}-id"] = ph.pk
        data[f"photos-{i}-occurrence"] = occ.pk
        for k, v in (rows or {}).get(ph.pk, {}).items():
            data[f"photos-{i}-{k}"] = v
    return data


@override_settings(MEDIA_ROOT=MEDIA)
class Photos(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.taxon = Taxon.objects.create(scientific_name="Milnesium tardigradum")

    def test_넣을_때_여러_장을_올리고_섬네일을_만든다(self):
        res = self.client.post(reverse("occurrences:create"), {
            **form_data(self.taxon, locality="남산"),
            "new_photos": [image_file("a.png"), image_file("b.jpg", fmt="JPEG")],
        })
        occ = Occurrence.objects.get(locality="남산")
        self.assertRedirects(res, reverse("occurrences:detail", args=[occ.pk]))
        photos = list(occ.photos.all())
        self.assertEqual(len(photos), 2)
        with Image.open(photos[0].thumbnail.path) as th:
            self.assertEqual(th.format, "JPEG")
            self.assertEqual(max(th.size), Photo.THUMBNAIL_SIZE)
        self.assertTrue(photos[0].image.name.startswith(f"photos/{occ.pk}/"))

    def test_투명한_PNG_도_섬네일이_된다(self):
        occ = Occurrence.objects.create(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0)
        ph = Photo.objects.create(occurrence=occ, image=image_file(mode="RGBA", color=(0, 0, 0, 0)))
        with Image.open(ph.thumbnail.path) as th:
            self.assertEqual(th.getpixel((0, 0)), (255, 255, 255))

    def test_그림이_아니면_받지_않는다(self):
        bad = SimpleUploadedFile("note.png", b"not an image", content_type="image/png")
        res = self.client.post(reverse("occurrences:create"), {**form_data(self.taxon), "new_photos": [bad]})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["form"].errors["new_photos"])
        self.assertFalse(Occurrence.objects.exists())

    @override_settings(MAX_PHOTO_MB=0)
    def test_크기_한계를_넘으면_받지_않는다(self):
        res = self.client.post(reverse("occurrences:create"), {**form_data(self.taxon), "new_photos": [image_file()]})
        self.assertIn("MB", str(res.context["form"].errors["new_photos"]))

    def test_GeoJSON_에_첫_섬네일과_장수가_실린다(self):
        occ = Occurrence.objects.create(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0)
        first = Photo.objects.create(occurrence=occ, image=image_file("1.png"))
        Photo.objects.create(occurrence=occ, image=image_file("2.png"))
        Occurrence.objects.create(taxon=self.taxon, decimal_latitude=1, decimal_longitude=1)
        with self.assertNumQueries(2):   # 산출 + 사진 한 번씩. 점 수만큼 늘지 않는다
            features = self.client.get(reverse("occurrences:geojson")).json()["features"]
        by_id = {f["id"]: f["properties"] for f in features}
        self.assertEqual(by_id[occ.pk]["photo"], first.thumbnail.url)
        self.assertEqual(by_id[occ.pk]["photo_count"], 2)
        self.assertIsNone(next(p for i, p in by_id.items() if i != occ.pk)["photo"])

    def test_고치며_설명을_적고_한_장을_빼고_한_장을_더한다(self):
        occ = Occurrence.objects.create(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0)
        keep = Photo.objects.create(occurrence=occ, image=image_file("keep.png"))
        drop = Photo.objects.create(occurrence=occ, image=image_file("drop.png"))
        drop_files = [Path(drop.image.path), Path(drop.thumbnail.path)]
        res = self.client.post(reverse("occurrences:update", args=[occ.pk]), {
            **form_data(self.taxon),
            **formset_data(occ, {keep.pk: {"description": "배면, ×400", "license": "CC BY 4.0"},
                                 drop.pk: {"DELETE": "on"}}),
            "new_photos": [image_file("new.png")],
        })
        self.assertRedirects(res, reverse("occurrences:detail", args=[occ.pk]))
        keep.refresh_from_db()
        self.assertEqual(keep.description, "배면, ×400")
        self.assertEqual(occ.photos.count(), 2)
        self.assertFalse(Photo.objects.filter(pk=drop.pk).exists())
        self.assertFalse(any(f.exists() for f in drop_files))

    def test_산출을_지우면_사진_파일도_지운다(self):
        occ = Occurrence.objects.create(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0)
        ph = Photo.objects.create(occurrence=occ, image=image_file())
        files = [Path(ph.image.path), Path(ph.thumbnail.path)]
        self.assertTrue(all(f.exists() for f in files))
        self.client.post(reverse("occurrences:delete", args=[occ.pk]))
        self.assertFalse(Photo.objects.exists())
        self.assertFalse(any(f.exists() for f in files))

    def test_자세히_화면에_사진이_보이고_원본이_내려온다(self):
        occ = Occurrence.objects.create(taxon=self.taxon, decimal_latitude=0, decimal_longitude=0)
        ph = Photo.objects.create(occurrence=occ, image=image_file(), description="이끼 위")
        res = self.client.get(reverse("occurrences:detail", args=[occ.pk]))
        self.assertContains(res, ph.thumbnail.url)
        self.assertContains(res, "이끼 위")
        res = self.client.get(ph.image.url)
        self.assertEqual(res.status_code, 200)
