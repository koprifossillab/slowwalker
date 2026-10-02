"""완보동물 산출 기록.

```
분류군   Taxon       문·강·목·과·속·종 … 위아래로 잇는다(parent)
 └ 산출   Occurrence  한 분류군이 한 자리(위경도 하나)에서 나왔다는 기록 하나
    └ 사진 Photo     산출 하나에 여러 장. 올릴 때 섬네일을 따로 만든다
```

칸 이름은 될 수 있는 한 Darwin Core(GBIF 가 쓰는 말)를 따른다 — 훗날 GBIF 로 내보내거나
받아들일 때 이름을 옮겨 적기만 하면 되게 하려는 것이다. 공간 연산은 하지 않으므로
GeoDjango 를 쓰지 않고 위경도를 숫자 두 칸으로 둔다 (GSM 의 점묶음과 같다).
"""
from io import BytesIO
from pathlib import PurePath

from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from PIL import Image, ImageOps


class Taxon(models.Model):
    class Rank(models.TextChoices):
        PHYLUM = "phylum", "문"
        CLASS = "class", "강"
        ORDER = "order", "목"
        SUPERFAMILY = "superfamily", "상과"
        FAMILY = "family", "과"
        SUBFAMILY = "subfamily", "아과"
        GENUS = "genus", "속"
        SPECIES = "species", "종"
        SUBSPECIES = "subspecies", "아종"

    scientific_name = models.CharField("학명", max_length=200)
    authorship = models.CharField("명명자", max_length=200, blank=True,
                                  help_text="예: (Doyère, 1840)")
    rank = models.CharField("계급", max_length=20, choices=Rank.choices, default=Rank.SPECIES)
    parent = models.ForeignKey("self", verbose_name="상위 분류군", null=True, blank=True,
                               on_delete=models.PROTECT, related_name="children")

    class Meta:
        verbose_name = "분류군"
        verbose_name_plural = "분류군"
        ordering = ["scientific_name"]
        constraints = [
            models.UniqueConstraint(fields=["scientific_name", "rank"], name="uniq_taxon_name_rank"),
        ]

    def __str__(self):
        return f"{self.scientific_name} {self.authorship}".strip()


class Occurrence(models.Model):
    class BasisOfRecord(models.TextChoices):
        PRESERVED = "PreservedSpecimen", "표본"
        MATERIAL = "MaterialSample", "시료"
        HUMAN = "HumanObservation", "관찰"
        LITERATURE = "MaterialCitation", "문헌 기록"

    taxon = models.ForeignKey(Taxon, verbose_name="분류군", on_delete=models.PROTECT,
                              related_name="occurrences")
    # 소수점 아래 6 자리 ≈ 0.1 m. 문헌 좌표는 대개 이보다 거칠다
    decimal_latitude = models.DecimalField(
        "위도", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    decimal_longitude = models.DecimalField(
        "경도", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])
    coordinate_uncertainty_m = models.PositiveIntegerField("좌표 불확도(m)", null=True, blank=True)
    country = models.CharField("나라", max_length=100, blank=True)
    locality = models.CharField("산지", max_length=300, blank=True)
    habitat = models.CharField("서식지", max_length=200, blank=True,
                               help_text="예: 이끼, 지의류, 담수 퇴적물, 해양 간극")
    elevation_m = models.IntegerField("고도(m)", null=True, blank=True)
    event_date = models.DateField("채집일", null=True, blank=True)
    recorded_by = models.CharField("채집자", max_length=200, blank=True)
    basis_of_record = models.CharField("기록 근거", max_length=30, choices=BasisOfRecord.choices,
                                       default=BasisOfRecord.PRESERVED)
    reference = models.TextField("출처 문헌", blank=True)
    remarks = models.TextField("비고", blank=True)
    created_at = models.DateTimeField("생긴 때", auto_now_add=True)
    updated_at = models.DateTimeField("고친 때", auto_now=True)

    class Meta:
        verbose_name = "산출"
        verbose_name_plural = "산출"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["decimal_latitude", "decimal_longitude"])]

    def __str__(self):
        return f"{self.taxon.scientific_name} @ {self.decimal_latitude}, {self.decimal_longitude}"

    def as_feature(self) -> dict:
        """GeoJSON Feature 하나. 좌표 순서는 GeoJSON 규약대로 [경도, 위도] 다.

        사진은 `prefetch_related("photos")` 로 미리 받아 두는 것을 전제로 한다 — 산출마다 물으면 점 수만큼 질의가 나간다.
        """
        photos = [p for p in self.photos.all() if p.thumbnail]
        return {
            "type": "Feature",
            "id": self.pk,
            "geometry": {
                "type": "Point",
                "coordinates": [float(self.decimal_longitude), float(self.decimal_latitude)],
            },
            "properties": {
                "taxon": self.taxon.scientific_name,
                "taxon_id": self.taxon_id,
                "country": self.country,
                "locality": self.locality,
                "habitat": self.habitat,
                "event_date": self.event_date.isoformat() if self.event_date else None,
                "basis_of_record": self.get_basis_of_record_display(),
                "reference": self.reference,
                # 지도에 커서를 올리면 띄우는 섬네일. 첫 장만 싣는다 — 목록 전부를 실으면 GeoJSON 이 불어난다
                "photo": photos[0].thumbnail.url if photos else None,
                "photo_count": len(photos),
            },
        }


def photo_path(photo, filename: str) -> str:
    """원본은 `photos/<산출 번호>/` 아래에. 이름은 올린 것을 따르되 같은 이름이면 Django 가 꼬리를 붙인다."""
    return f"photos/{photo.occurrence_id}/{PurePath(filename).name}"


def thumbnail_path(photo, filename: str) -> str:
    """섬네일은 원본 곁 `photos/<산출 번호>/thumbs/` 에."""
    return f"photos/{photo.occurrence_id}/thumbs/{PurePath(filename).name}"


class Photo(models.Model):
    """산출 하나의 사진. 칸 이름은 GBIF Simple Multimedia 확장(`description`·`creator`·`license`)을 따른다."""

    #: 섬네일의 긴 변(px). 지도의 커서 카드와 자세히 화면의 작은 그림이 이것을 쓴다
    THUMBNAIL_SIZE = 360

    occurrence = models.ForeignKey(Occurrence, verbose_name="산출", on_delete=models.CASCADE,
                                   related_name="photos")
    image = models.ImageField("사진", upload_to=photo_path)
    thumbnail = models.ImageField("섬네일", upload_to=thumbnail_path, editable=False, blank=True)
    description = models.CharField("설명", max_length=300, blank=True,
                                   help_text="예: 배면, 광학현미경 ×400")
    creator = models.CharField("찍은 이", max_length=200, blank=True)
    license = models.CharField("이용 허락", max_length=100, blank=True, help_text="예: CC BY 4.0")
    created_at = models.DateTimeField("올린 때", auto_now_add=True)

    class Meta:
        verbose_name = "사진"
        verbose_name_plural = "사진"
        ordering = ["id"]

    def __str__(self):
        return f"{self.occurrence} · {PurePath(self.image.name).name}"

    def save(self, *args, **kwargs):
        if self.image and not self.thumbnail:
            self.thumbnail.save(f"{PurePath(self.image.name).stem}.jpg", self.make_thumbnail(), save=False)
        super().save(*args, **kwargs)

    def make_thumbnail(self) -> ContentFile:
        """긴 변을 `THUMBNAIL_SIZE` 로 줄인 JPEG. 휴대전화 사진은 EXIF 방향대로 먼저 세운다."""
        self.image.open()
        self.image.seek(0)
        with Image.open(self.image) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE))
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                # 투명한 PNG 는 흰 바탕에 얹는다 — JPEG 에는 투명이 없다
                rgba = im.convert("RGBA")
                im = Image.new("RGB", im.size, "white")
                im.paste(rgba, mask=rgba.getchannel("A"))
            elif im.mode not in ("RGB", "L"):
                # 16 비트 TIFF·CMYK 따위 — JPEG 가 받는 꼴로
                im = im.convert("RGB")
            buf = BytesIO()
            im.save(buf, "JPEG", quality=85)
        self.image.seek(0)
        return ContentFile(buf.getvalue())


@receiver(post_delete, sender=Photo)
def _remove_photo_files(sender, instance, **kwargs):
    """사진 줄을 지우면 파일도 지운다. 산출을 지울 때(CASCADE)도 사진마다 불린다."""
    for f in (instance.image, instance.thumbnail):
        if f:
            f.storage.delete(f.name)
