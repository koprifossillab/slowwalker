"""산출(과 분류군)을 넣고 고치는 양식.

칸과 검사는 모델의 것을 그대로 쓴다 — 위경도의 범위 검사도 모델 `validators` 가 한다.
여기서는 브라우저가 알맞은 입력기(날짜·숫자)를 띄우게 위젯만 고른다.
"""
from django import forms
from django.conf import settings

from .models import Occurrence, Photo, Taxon


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """사진 여러 장을 한 칸으로 받는다. 한 장씩 Pillow 로 열어 보고 크기 한계를 잰다."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleImageInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        limit = settings.MAX_PHOTO_MB * 1024 * 1024
        cleaned = []
        for f in files:
            if f.size > limit:
                raise forms.ValidationError(f"{f.name} 은 {settings.MAX_PHOTO_MB} MB 를 넘는다.")
            cleaned.append(super().clean(f, initial))
        return cleaned


class OccurrenceForm(forms.ModelForm):
    class Meta:
        model = Occurrence
        fields = [
            "taxon", "basis_of_record",
            "decimal_latitude", "decimal_longitude", "coordinate_uncertainty_m",
            "country", "locality", "habitat", "elevation_m",
            "event_date", "recorded_by",
            "reference", "remarks",
        ]
        widgets = {
            # 소수 6 자리까지 받는다. step 을 "any" 로 두지 않으면 브라우저가 정수만 받는다
            "decimal_latitude": forms.NumberInput(attrs={"step": "any", "min": -90, "max": 90,
                                                         "placeholder": "예: 37.5665"}),
            "decimal_longitude": forms.NumberInput(attrs={"step": "any", "min": -180, "max": 180,
                                                          "placeholder": "예: 126.9780"}),
            "event_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "reference": forms.Textarea(attrs={"rows": 3}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    new_photos = MultipleImageField(label="사진 더하기", required=False,
                                    help_text="여러 장을 한꺼번에 고를 수 있다. JPEG·PNG·TIFF 따위.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_photos"].help_text += f" 한 장에 {settings.MAX_PHOTO_MB} MB 까지."
        # 학명 차례로 — 계급까지 보여야 같은 이름의 속·종이 갈린다
        self.fields["taxon"].queryset = Taxon.objects.order_by("scientific_name", "rank")
        self.fields["taxon"].label_from_instance = lambda t: f"{t} · {t.get_rank_display()}"


class TaxonForm(forms.ModelForm):
    """산출을 넣다가 목록에 없는 분류군을 곧바로 더하는 양식. 계층을 손보는 일은 관리 화면이 한다."""

    class Meta:
        model = Taxon
        fields = ["scientific_name", "authorship", "rank", "parent"]
        widgets = {"scientific_name": forms.TextInput(attrs={"placeholder": "예: Milnesium tardigradum"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = Taxon.objects.order_by("scientific_name", "rank")
        self.fields["parent"].label_from_instance = lambda t: f"{t.scientific_name} · {t.get_rank_display()}"


# 이미 붙은 사진의 설명·찍은 이·이용 허락을 고치고, 빼고 싶은 것을 고른다. 새 사진은 `new_photos` 로 받는다
PhotoFormSet = forms.inlineformset_factory(
    Occurrence, Photo, fields=["description", "creator", "license"], extra=0, can_delete=True)
