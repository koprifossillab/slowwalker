"""완보동물 채집과 산출 기록.

```
채집지 Site → 채집 CollectionEvent → 시료 Sample → 산출 Occurrence
분류군 Taxon 은 산출에서 참조하며 parent 로 문·강·목·과·속·종을 잇는다.
사진 Photo 는 채집지·시료·산출 중 한 곳에 속하고 섬네일을 따로 만든다.
기존 단독 산출의 좌표와 원본 정보는 그대로 보존한다.
```

칸 이름은 될 수 있는 한 Darwin Core(GBIF 가 쓰는 말)를 따른다 — 훗날 GBIF 로 내보내거나
받아들일 때 이름을 옮겨 적기만 하면 되게 하려는 것이다. 공간 연산은 하지 않으므로
GeoDjango 를 쓰지 않고 위경도를 숫자 두 칸으로 둔다 (GSM 의 점묶음과 같다).
"""
from io import BytesIO
from pathlib import PurePath

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
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


class Site(models.Model):
    """같은 산지의 반복 채집을 묶는 자리. 좌표가 같아도 서로 다른 산지일 수 있다."""

    class Realm(models.TextChoices):
        MARINE = "marine", "해양"
        TERRESTRIAL = "terrestrial", "육상"
        FRESHWATER = "freshwater", "담수"
        UNKNOWN = "unknown", "미지정"

    name = models.CharField("채집지 이름", max_length=200)
    locality = models.CharField("산지 상세", max_length=300, blank=True)
    decimal_latitude = models.DecimalField("위도", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    decimal_longitude = models.DecimalField("경도", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])
    coordinate_uncertainty_m = models.PositiveIntegerField("좌표 불확도(m)", null=True, blank=True,
        validators=[MinValueValidator(1)])
    country = models.CharField("나라", max_length=100, blank=True)
    realm = models.CharField("환경 구분", max_length=20, choices=Realm.choices, default=Realm.UNKNOWN)
    habitat = models.CharField("서식지", max_length=200, blank=True)
    remarks = models.TextField("비고", blank=True)

    class Meta:
        verbose_name = "채집지"
        verbose_name_plural = "채집지"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class CollectionEvent(models.Model):
    site = models.ForeignKey(Site, verbose_name="채집지", on_delete=models.PROTECT, related_name="events")
    event_date = models.DateField("채집일", null=True, blank=True,
        help_text="정확한 날짜를 아는 경우만 입력한다. 일부만 알려진 날짜는 채집일 원문에 남긴다.")
    event_date_verbatim = models.CharField("채집일 원문", max_length=200, blank=True,
        help_text="예: 1998년, 2025년 5~6월. 정확한 날짜를 모르면 채집일은 비우고 여기에 적는다.")
    recorded_by = models.CharField("채집자", max_length=200, blank=True)
    sampling_protocol = models.TextField("채집 방법", blank=True)
    sampling_effort = models.CharField("채집 노력량", max_length=200, blank=True,
        help_text="예: 30분, 따개비 10개, 이끼 10 g. 단위를 함께 적는다.")
    reference = models.TextField("출처 문헌", blank=True)
    remarks = models.TextField("비고", blank=True)

    class Meta:
        verbose_name = "채집"
        verbose_name_plural = "채집"
        ordering = ["-event_date", "-id"]

    def __str__(self):
        return f"{self.site} · {self.event_date or '날짜 미상'} · 채집 #{self.pk or '새 기록'}"


class Sample(models.Model):
    event = models.ForeignKey(CollectionEvent, verbose_name="채집", on_delete=models.PROTECT,
        related_name="samples")
    sample_code = models.CharField("시료 번호", max_length=100,
        help_text="연구실에서 쓰는 표본·시료 번호. 한 채집 안에서 중복되지 않게 적는다.")
    substrate = models.CharField("채집 기질", max_length=200, blank=True,
        help_text="예: 따개비, 이끼, 모래")
    host_taxon = models.CharField("숙주·기질 생물 학명", max_length=200, blank=True,
        help_text="예: 채집한 따개비의 학명. 완보동물 학명은 산출에 적는다.")
    description = models.TextField("시료 설명", blank=True)

    class Meta:
        verbose_name = "시료"
        verbose_name_plural = "시료"
        ordering = ["sample_code", "id"]
        constraints = [models.UniqueConstraint(fields=["event", "sample_code"], name="uniq_sample_code_event")]

    def __str__(self):
        return f"{self.sample_code} · {self.event}"


class Occurrence(models.Model):
    class BasisOfRecord(models.TextChoices):
        PRESERVED = "PreservedSpecimen", "표본"
        MATERIAL = "MaterialSample", "시료"
        HUMAN = "HumanObservation", "관찰"
        LITERATURE = "MaterialCitation", "문헌 기록"

    taxon = models.ForeignKey(Taxon, verbose_name="분류군", on_delete=models.PROTECT,
                              related_name="occurrences")
    sample = models.ForeignKey(Sample, verbose_name="시료", on_delete=models.PROTECT,
        null=True, blank=True, related_name="occurrences",
        help_text="시료를 연결하면 산지·좌표·채집일·채집자는 해당 채집의 정보를 사용한다.")
    individual_count = models.PositiveIntegerField("개체 수", null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text="확인한 개체 수(1 이상). 미계수는 비워 둔다. 미산출·부재는 이 칸으로 기록하지 않는다.")
    identified_by = models.CharField("동정자", max_length=200, blank=True)
    identification_qualifier = models.CharField("동정 한정어", max_length=100, blank=True,
        help_text="예: cf., aff., sp.")
    # 소수점 아래 6 자리 ≈ 0.1 m. 문헌 좌표는 대개 이보다 거칠다
    decimal_latitude = models.DecimalField(
        "위도", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    decimal_longitude = models.DecimalField(
        "경도", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])
    # 기존 자료의 0 도 그대로 보존한다. 새 입력의 양수 검사는 양식이 맡는다.
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
        constraints = [models.CheckConstraint(
            condition=models.Q(sample__isnull=False) | models.Q(decimal_latitude__isnull=False, decimal_longitude__isnull=False),
            name="occurrence_sample_or_coordinates")]

    def __str__(self):
        return f"{self.taxon.scientific_name} @ {self.effective_latitude}, {self.effective_longitude}"

    def clean(self):
        super().clean()
        if not self.sample_id:
            errors = {name: "시료에 연결하지 않은 산출은 좌표가 필요하다."
                      for name in ("decimal_latitude", "decimal_longitude") if getattr(self, name) is None}
            if errors:
                raise ValidationError(errors)

    @property
    def source_site(self):
        return self.sample.event.site if self.sample_id else None

    @property
    def source_event(self):
        return self.sample.event if self.sample_id else None

    def _site_value(self, field):
        return getattr(self.source_site if self.sample_id else self, field)

    def _event_value(self, field):
        return getattr(self.source_event if self.sample_id else self, field)

    effective_latitude = property(lambda self: self._site_value("decimal_latitude"))
    effective_longitude = property(lambda self: self._site_value("decimal_longitude"))
    effective_uncertainty = property(lambda self: self._site_value("coordinate_uncertainty_m"))
    effective_country = property(lambda self: self._site_value("country"))
    effective_locality = property(lambda self: (self.source_site.locality or self.source_site.name)
                                  if self.sample_id else self.locality)
    effective_habitat = property(lambda self: self._site_value("habitat"))
    effective_event_date = property(lambda self: self._event_value("event_date"))
    effective_recorded_by = property(lambda self: self._event_value("recorded_by"))
    effective_reference = property(lambda self: self.reference or self._event_value("reference"))

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
                "coordinates": [float(self.effective_longitude), float(self.effective_latitude)],
            },
            "properties": {
                "taxon": self.taxon.scientific_name,
                "taxon_id": self.taxon_id,
                "country": self.effective_country,
                "locality": self.effective_locality,
                "habitat": self.effective_habitat,
                "event_date": self.effective_event_date.isoformat() if self.effective_event_date else None,
                "basis_of_record": self.get_basis_of_record_display(),
                "reference": self.effective_reference,
                "coordinate_source": "site" if self.sample_id else "occurrence",
                # 지도에 커서를 올리면 띄우는 섬네일. 첫 장만 싣는다 — 목록 전부를 실으면 GeoJSON 이 불어난다
                "photo": photos[0].thumbnail.url if photos else None,
                "photo_count": len(photos),
            },
        }


def photo_path(photo, filename: str) -> str:
    """원본은 `photos/<산출 번호>/` 아래에. 이름은 올린 것을 따르되 같은 이름이면 Django 가 꼬리를 붙인다."""
    return f"{photo_directory(photo)}/{PurePath(filename).name}"


def thumbnail_path(photo, filename: str) -> str:
    """섬네일은 원본 곁 `photos/<산출 번호>/thumbs/` 에."""
    return f"{photo_directory(photo)}/thumbs/{PurePath(filename).name}"


def photo_directory(photo):
    # 기존 산출 사진의 경로는 그대로 둔다.
    if photo.site_id:
        return f"photos/sites/{photo.site_id}"
    if photo.sample_id:
        return f"photos/samples/{photo.sample_id}"
    return f"photos/{photo.occurrence_id}"


class Photo(models.Model):
    """채집지·시료·산출 중 한 곳의 사진. GBIF Simple Multimedia 의 칸 이름을 따른다."""

    #: 섬네일의 긴 변(px). 지도의 커서 카드와 자세히 화면의 작은 그림이 이것을 쓴다
    THUMBNAIL_SIZE = 360

    occurrence = models.ForeignKey(Occurrence, verbose_name="산출", on_delete=models.CASCADE,
                                   related_name="photos", null=True, blank=True)
    site = models.ForeignKey(Site, verbose_name="채집지", on_delete=models.CASCADE,
        related_name="photos", null=True, blank=True)
    sample = models.ForeignKey(Sample, verbose_name="시료", on_delete=models.CASCADE,
        related_name="photos", null=True, blank=True)
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
        constraints = [models.CheckConstraint(condition=(
            models.Q(occurrence__isnull=False, site__isnull=True, sample__isnull=True)
            | models.Q(occurrence__isnull=True, site__isnull=False, sample__isnull=True)
            | models.Q(occurrence__isnull=True, site__isnull=True, sample__isnull=False)),
            name="photo_exactly_one_owner")]

    def __str__(self):
        return f"{self.occurrence or self.site or self.sample} · {PurePath(self.image.name).name}"

    def clean(self):
        super().clean()
        # 관리 화면의 새 부모는 아직 PK 가 없으므로 캐시된 관계 객체도 센다.
        if sum(getattr(self, name) is not None for name in ("occurrence", "site", "sample")) != 1:
            raise ValidationError("사진은 채집지·시료·산출 중 한 곳에만 연결해야 한다.")

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
