from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import generic

from slowwalkerweb.version import VERSION

from .forms import (CollectionEventForm, OccurrenceForm, PhotoFormSet, SampleForm,
                    SamplePhotoFormSet, SiteForm, SitePhotoFormSet, TaxonForm)
from .models import CollectionEvent, Occurrence, Photo, Sample, Site, Taxon


def map_view(request):
    """세계지도. 점은 브라우저가 `occurrences.geojson` 에서 받아 그린다."""
    return render(request, "occurrences/map.html")


def occurrences_geojson(request):
    """산출 전부를 GeoJSON FeatureCollection 으로.

    `?taxon=<id>` 로 분류군 하나만 거른다. 기록이 수만 개를 넘으면 범위(bbox)로 자르는
    것을 더한다 — 지금은 통째로 낸다.
    """
    qs = occurrence_queryset()
    taxon = request.GET.get("taxon")
    if taxon:
        if not taxon.isdigit():
            return JsonResponse({"error": "taxon 은 숫자여야 한다"}, status=400)
        qs = qs.filter(taxon_id=int(taxon))
    return JsonResponse({
        "type": "FeatureCollection",
        "features": [o.as_feature() for o in qs],
    })


def occurrence_queryset():
    return Occurrence.objects.select_related("taxon", "sample__event__site").prefetch_related("photos")


def site_queryset():
    return Site.objects.prefetch_related("photos", "events__samples__photos",
        "events__samples__occurrences__taxon", "events__samples__occurrences__photos")


def photos_data(owner):
    return [{"url": p.image.url, "thumbnail": p.thumbnail.url if p.thumbnail else p.image.url,
             "description": p.description, "creator": p.creator, "license": p.license}
            for p in owner.photos.all() if p.image]


def occurrence_data_dict(occ):
    event_date = occ.effective_event_date
    return {
        "kind": "occurrence", "id": occ.pk, "name": occ.taxon.scientific_name,
        "taxon": occ.taxon.scientific_name, "taxon_id": occ.taxon_id,
        "locality": occ.effective_locality, "country": occ.effective_country,
        "habitat": occ.effective_habitat, "realm": occ.source_site.realm if occ.sample_id else "unknown",
        "latitude": float(occ.effective_latitude), "longitude": float(occ.effective_longitude),
        "coordinate_uncertainty_m": occ.effective_uncertainty,
        "coordinate_source": "site" if occ.sample_id else "occurrence",
        "sample_id": occ.sample_id, "event_date": event_date.isoformat() if event_date else None,
        "event_date_verbatim": occ.source_event.event_date_verbatim if occ.sample_id else "",
        "recorded_by": occ.effective_recorded_by, "reference": occ.effective_reference,
        "remarks": occ.remarks, "basis_of_record": occ.get_basis_of_record_display(),
        "individual_count": occ.individual_count, "identified_by": occ.identified_by,
        "identification_qualifier": occ.identification_qualifier, "photos": photos_data(occ),
        "detail_url": reverse("occurrences:detail", args=[occ.pk]),
        "edit_url": reverse("occurrences:update", args=[occ.pk]),
    }


def occurrence_data(request, pk):
    return JsonResponse(occurrence_data_dict(get_object_or_404(occurrence_queryset(), pk=pk)))


def site_data_dict(site):
    events = []
    for event in site.events.all():
        samples = []
        for sample in event.samples.all():
            samples.append({
                "id": sample.pk, "sample_code": sample.sample_code, "substrate": sample.substrate,
                "host_taxon": sample.host_taxon, "description": sample.description,
                "photos": photos_data(sample),
                "detail_url": reverse("occurrences:sample_detail", args=[sample.pk]),
                "edit_url": reverse("occurrences:sample_update", args=[sample.pk]),
                "occurrence_create_url": f"{reverse('occurrences:create')}?sample={sample.pk}",
                # 여기서는 부모 채집지 정보를 다시 읽지 않고 산출 자체 정보만 전한다.
                "occurrences": [{"id": occ.pk, "taxon": occ.taxon.scientific_name,
                    "individual_count": occ.individual_count, "identified_by": occ.identified_by,
                    "identification_qualifier": occ.identification_qualifier, "remarks": occ.remarks,
                    "basis_of_record": occ.get_basis_of_record_display(), "reference": occ.reference,
                    "photos": photos_data(occ),
                    "detail_url": reverse("occurrences:detail", args=[occ.pk]),
                    "edit_url": reverse("occurrences:update", args=[occ.pk])}
                    for occ in sample.occurrences.all()],
            })
        events.append({"id": event.pk, "event_date": event.event_date.isoformat() if event.event_date else None,
            "event_date_verbatim": event.event_date_verbatim, "recorded_by": event.recorded_by,
            "sampling_protocol": event.sampling_protocol, "sampling_effort": event.sampling_effort,
            "reference": event.reference, "remarks": event.remarks, "samples": samples,
            "detail_url": reverse("occurrences:event_detail", args=[event.pk]),
            "edit_url": reverse("occurrences:event_update", args=[event.pk]),
            "sample_create_url": f"{reverse('occurrences:sample_create')}?event={event.pk}"})
    return {
        "kind": "site", "id": site.pk, "name": site.name, "locality": site.locality,
        "latitude": float(site.decimal_latitude), "longitude": float(site.decimal_longitude),
        "coordinate_uncertainty_m": site.coordinate_uncertainty_m, "country": site.country,
        "realm": site.realm, "habitat": site.habitat, "remarks": site.remarks,
        "photos": photos_data(site), "events": events,
        "detail_url": reverse("occurrences:site_detail", args=[site.pk]),
        "edit_url": reverse("occurrences:site_update", args=[site.pk]),
        "event_create_url": f"{reverse('occurrences:event_create')}?site={site.pk}",
    }


def site_data(request, pk):
    return JsonResponse(site_data_dict(get_object_or_404(site_queryset(), pk=pk)))


def map_data(request):
    """채집지당 한 점. 이전 단독 산출은 원래 좌표에 남겨 같은 좌표라도 합치지 않는다."""
    sites = site_queryset()
    legacy = occurrence_queryset().filter(sample__isnull=True)
    taxon = request.GET.get("taxon", "")
    if taxon:
        if not taxon.isdigit():
            return JsonResponse({"error": "taxon 은 숫자여야 한다"}, status=400)
        sites = sites.filter(events__samples__occurrences__taxon_id=int(taxon)).distinct()
        legacy = legacy.filter(taxon_id=int(taxon))
    features = []
    for site in sites:
        events = list(site.events.all())
        samples = [sample for event in events for sample in event.samples.all()]
        occurrences = [occ for sample in samples for occ in sample.occurrences.all()]
        photos = photos_data(site)
        features.append({"type": "Feature", "id": f"site:{site.pk}",
            "geometry": {"type": "Point", "coordinates": [float(site.decimal_longitude), float(site.decimal_latitude)]},
            "properties": {"kind": "site", "id": site.pk, "name": site.name,
                "locality": site.locality, "country": site.country, "habitat": site.habitat, "realm": site.realm,
                "event_count": len(events), "sample_count": len(samples), "occurrence_count": len(occurrences),
                "taxa": sorted({occ.taxon.scientific_name for occ in occurrences}),
                "detail_url": reverse("occurrences:site_detail", args=[site.pk]),
                "edit_url": reverse("occurrences:site_update", args=[site.pk]),
                "data_url": reverse("occurrences:site_data", args=[site.pk]),
                "photo": photos[0]["thumbnail"] if photos else None}})
    for occ in legacy:
        feature = occ.as_feature()
        feature["id"] = f"occurrence:{occ.pk}"
        feature["properties"].update({"kind": "occurrence", "id": occ.pk,
            "name": occ.locality or occ.taxon.scientific_name, "realm": "unknown",
            "event_count": 0, "sample_count": 0, "occurrence_count": 1,
            "taxa": [occ.taxon.scientific_name],
            "detail_url": reverse("occurrences:detail", args=[occ.pk]),
            "edit_url": reverse("occurrences:update", args=[occ.pk]),
            "data_url": reverse("occurrences:occurrence_data", args=[occ.pk])})
        features.append(feature)
    return JsonResponse({"type": "FeatureCollection", "features": features})


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


# ── 산출을 넣고 고치는 화면 ──
#
# 보기(목록·자세히)는 언제나 누구나 한다. 넣기·고치기·지우기는 `EDIT_REQUIRES_LOGIN` 이 켜져 있을 때만
# 로그인을 묻는다 — 연구소 안에서 시험하는 동안은 꺼 둔다(누구나 고친다).


class EditPermission(LoginRequiredMixin):
    """`EDIT_REQUIRES_LOGIN` 이 꺼져 있으면 로그인을 묻지 않는다."""

    def dispatch(self, request, *args, **kwargs):
        if not settings.EDIT_REQUIRES_LOGIN:
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

class OccurrenceList(generic.ListView):
    """산출 목록. `q` 는 학명·나라·산지·서식지·출처에서 찾고, `taxon` 은 분류군 하나로 거른다."""
    model = Occurrence
    template_name = "occurrences/occurrence_list.html"
    paginate_by = 50

    def get_queryset(self):
        qs = occurrence_queryset().order_by("-updated_at")
        q = self.request.GET.get("q", "").strip()
        if q:
            legacy = Q(sample__isnull=True) & (Q(country__icontains=q) | Q(locality__icontains=q)
                        | Q(habitat__icontains=q) | Q(reference__icontains=q))
            linked = (Q(sample__event__site__name__icontains=q) | Q(sample__event__site__country__icontains=q)
                | Q(sample__event__site__locality__icontains=q) | Q(sample__event__site__habitat__icontains=q)
                | Q(sample__event__reference__icontains=q) | Q(sample__sample_code__icontains=q))
            qs = qs.filter(Q(taxon__scientific_name__icontains=q) | Q(reference__icontains=q) | legacy | linked)
        taxon = self.request.GET.get("taxon", "")
        if taxon.isdigit():
            qs = qs.filter(taxon_id=int(taxon))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        taxon = self.request.GET.get("taxon", "")
        ctx.update(
            q=self.request.GET.get("q", "").strip(),
            taxon_id=int(taxon) if taxon.isdigit() else None,
            # 산출이 있는 분류군만 고르개에 올린다
            taxa=Taxon.objects.filter(occurrences__isnull=False).distinct().order_by("scientific_name"),
        )
        # 쪽을 넘겨도 거르기가 남게 — page 를 뺀 나머지 물음표
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class OccurrenceDetail(generic.DetailView):
    model = Occurrence
    template_name = "occurrences/occurrence_detail.html"
    queryset = occurrence_queryset()


class SavesPhotos:
    """넣기·고치기가 함께 쓴다 — 양식의 `new_photos` 를 사진 줄로 만든다."""

    photo_owner_field = "occurrence"

    def save_new_photos(self, form) -> int:
        files = form.cleaned_data.get("new_photos") or []
        for f in files:
            Photo.objects.create(**{self.photo_owner_field: self.object}, image=f)
        return len(files)


class OccurrenceCreate(EditPermission, SavesPhotos, generic.CreateView):
    model = Occurrence
    form_class = OccurrenceForm
    template_name = "occurrences/occurrence_form.html"

    def get_initial(self):
        # 지도나 목록에서 분류군을 고른 채 왔으면 그대로 채운다
        initial = super().get_initial()
        for name, model in (("taxon", Taxon), ("sample", Sample)):
            value = self.request.GET.get(name, "")
            if value.isdigit() and model.objects.filter(pk=int(value)).exists():
                initial[name] = int(value)
        if "sample" not in initial:
            initial.update(coordinate_initial(self.request.GET))
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            n = self.save_new_photos(form)
        messages.success(self.request, f"산출을 넣었다{f' (사진 {n}장)' if n else ''}.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("occurrences:detail", args=[self.object.pk])


class OccurrenceUpdate(EditPermission, SavesPhotos, generic.UpdateView):
    """산출 칸과, 이미 붙은 사진(설명 고치기·빼기), 새 사진을 한 번에 저장한다."""
    model = Occurrence
    form_class = OccurrenceForm
    template_name = "occurrences/occurrence_form.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("photo_formset", PhotoFormSet(instance=self.object))
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = PhotoFormSet(request.POST, instance=self.object)
        if not (form.is_valid() and formset.is_valid()):
            return self.render_to_response(self.get_context_data(form=form, photo_formset=formset))
        with transaction.atomic():
            self.object = form.save()
            formset.save()   # 뺀 사진은 여기서 지워지고, 파일은 post_delete 가 지운다
            n = self.save_new_photos(form)
        gone = len(formset.deleted_objects)
        notes = [f"사진 {n}장 더함"] * bool(n) + [f"사진 {gone}장 뺌"] * bool(gone)
        messages.success(self.request, f"산출을 고쳤다{f' ({', '.join(notes)})' if notes else ''}.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("occurrences:detail", args=[self.object.pk])


class OccurrenceDelete(EditPermission, generic.DeleteView):
    model = Occurrence
    template_name = "occurrences/occurrence_confirm_delete.html"
    success_url = reverse_lazy("occurrences:list")

    def form_valid(self, form):
        messages.success(self.request, f"산출 #{self.object.pk} 를 지웠다.")
        return super().form_valid(form)


class TaxonCreate(EditPermission, generic.CreateView):
    """새 분류군. 산출 입력 화면에서 오면(`next`) 저장한 뒤 그 분류군을 고른 채로 돌아간다."""
    model = Taxon
    form_class = TaxonForm
    template_name = "occurrences/taxon_form.html"

    def next_url(self):
        url = self.request.POST.get("next") or self.request.GET.get("next") or ""
        # 바깥 주소로는 보내지 않는다
        ok = url_has_allowed_host_and_scheme(url, allowed_hosts={self.request.get_host()},
                                             require_https=self.request.is_secure())
        return url if ok else reverse("occurrences:create")

    def get_context_data(self, **kwargs):
        return super().get_context_data(next=self.next_url(), **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"분류군 {form.instance.scientific_name} 을 더했다.")
        return super().form_valid(form)

    def get_success_url(self):
        url = self.next_url()
        # 시료에서 산출을 넣던 흐름은 유지한다. 검증된 로컬 URL 에 분류군만 바꾼다.
        if url.split("?")[0] == reverse("occurrences:create"):
            parts = urlsplit(url)
            params = dict(parse_qsl(parts.query))
            params["taxon"] = self.object.pk
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))
        return url



def coordinate_initial(params):
    """지도에서 온 좌표만 검증해 미리 채운다. 잘못된 값은 저장하거나 추정하지 않는다."""
    initial = {}
    for field, aliases, limit in (("decimal_latitude", ("lat", "latitude"), 90),
                                  ("decimal_longitude", ("lon", "longitude"), 180)):
        raw = params.get(field) or next((params.get(key) for key in aliases if params.get(key)), None)
        if raw is None:
            continue
        try:
            value = Decimal(raw)
            if value.is_finite() and -limit <= value <= limit:
                initial[field] = value.quantize(Decimal("0.000001"))
        except (InvalidOperation, ValueError):
            pass
    return initial


class SamplingFormMixin(SavesPhotos):
    """채집지·채집·시료 양식. 사진은 해당 자료에만 붙인다."""
    template_name = "occurrences/sampling_form.html"
    photo_formset_class = None
    entity_label = ""
    detail_route = ""
    parent_field = None
    parent_model = None

    def get_initial(self):
        initial = super().get_initial()
        if self.parent_field:
            value = self.request.GET.get(self.parent_field, "")
            if value.isdigit() and self.parent_model.objects.filter(pk=int(value)).exists():
                initial[self.parent_field] = int(value)
        if self.model is Site:
            initial.update(coordinate_initial(self.request.GET))
            realm = self.request.GET.get("realm", "")
            if realm in Site.Realm.values:
                initial["realm"] = realm
        return initial

    def get_context_data(self, **kwargs):
        if self.object and self.photo_formset_class:
            kwargs.setdefault("photo_formset", self.photo_formset_class(instance=self.object))
        return super().get_context_data(entity_label=self.entity_label,
            is_site=self.model is Site, is_event=self.model is CollectionEvent, is_sample=self.model is Sample,
            **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            self.save_new_photos(form)
        messages.success(self.request, f"{self.entity_label} 정보를 저장했다.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.detail_route, args=[self.object.pk])


class SamplingUpdateMixin(SamplingFormMixin):
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.photo_formset_class:
            return super().post(request, *args, **kwargs)
        form = self.get_form()
        formset = self.photo_formset_class(request.POST, instance=self.object)
        form_valid = form.is_valid()
        formset_valid = formset.is_valid()
        if not (form_valid and formset_valid):
            return self.render_to_response(self.get_context_data(form=form, photo_formset=formset))
        with transaction.atomic():
            self.object = form.save()
            formset.save()
            self.save_new_photos(form)
        messages.success(self.request, f"{self.entity_label} 정보를 고쳤다.")
        return redirect(self.get_success_url())


class SiteCreate(EditPermission, SamplingFormMixin, generic.CreateView):
    model = Site
    form_class = SiteForm
    photo_owner_field = "site"
    entity_label = "채집지"
    detail_route = "occurrences:site_detail"


class SiteUpdate(EditPermission, SamplingUpdateMixin, generic.UpdateView):
    model = Site
    form_class = SiteForm
    photo_owner_field = "site"
    photo_formset_class = SitePhotoFormSet
    entity_label = "채집지"
    detail_route = "occurrences:site_detail"


class SiteDetail(generic.DetailView):
    model = Site
    queryset = site_queryset()
    template_name = "occurrences/site_detail.html"


class EventCreate(EditPermission, SamplingFormMixin, generic.CreateView):
    model = CollectionEvent
    form_class = CollectionEventForm
    entity_label = "채집"
    detail_route = "occurrences:event_detail"
    parent_field = "site"
    parent_model = Site


class EventUpdate(EditPermission, SamplingUpdateMixin, generic.UpdateView):
    model = CollectionEvent
    form_class = CollectionEventForm
    entity_label = "채집"
    detail_route = "occurrences:event_detail"


class EventDetail(generic.DetailView):
    model = CollectionEvent
    queryset = CollectionEvent.objects.select_related("site").prefetch_related("samples__occurrences__taxon")
    template_name = "occurrences/event_detail.html"


class SampleCreate(EditPermission, SamplingFormMixin, generic.CreateView):
    model = Sample
    form_class = SampleForm
    photo_owner_field = "sample"
    entity_label = "시료"
    detail_route = "occurrences:sample_detail"
    parent_field = "event"
    parent_model = CollectionEvent


class SampleUpdate(EditPermission, SamplingUpdateMixin, generic.UpdateView):
    model = Sample
    form_class = SampleForm
    photo_owner_field = "sample"
    photo_formset_class = SamplePhotoFormSet
    entity_label = "시료"
    detail_route = "occurrences:sample_detail"


class SampleDetail(generic.DetailView):
    model = Sample
    queryset = Sample.objects.select_related("event__site").prefetch_related("photos", "occurrences__taxon", "occurrences__photos")
    template_name = "occurrences/sample_detail.html"
