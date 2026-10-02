from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import generic

from slowwalkerweb.version import VERSION

from .forms import OccurrenceForm, PhotoFormSet, TaxonForm
from .models import Occurrence, Photo, Taxon


def map_view(request):
    """세계지도. 점은 브라우저가 `occurrences.geojson` 에서 받아 그린다."""
    return render(request, "occurrences/map.html")


def occurrences_geojson(request):
    """산출 전부를 GeoJSON FeatureCollection 으로.

    `?taxon=<id>` 로 분류군 하나만 거른다. 기록이 수만 개를 넘으면 범위(bbox)로 자르는
    것을 더한다 — 지금은 통째로 낸다.
    """
    qs = Occurrence.objects.select_related("taxon").prefetch_related("photos")
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
        qs = Occurrence.objects.select_related("taxon").order_by("-updated_at")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(taxon__scientific_name__icontains=q) | Q(country__icontains=q)
                           | Q(locality__icontains=q) | Q(habitat__icontains=q)
                           | Q(reference__icontains=q))
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
    queryset = Occurrence.objects.select_related("taxon").prefetch_related("photos")


class SavesPhotos:
    """넣기·고치기가 함께 쓴다 — 양식의 `new_photos` 를 사진 줄로 만든다."""

    def save_new_photos(self, form) -> int:
        files = form.cleaned_data.get("new_photos") or []
        for f in files:
            Photo.objects.create(occurrence=self.object, image=f)
        return len(files)


class OccurrenceCreate(EditPermission, SavesPhotos, generic.CreateView):
    model = Occurrence
    form_class = OccurrenceForm
    template_name = "occurrences/occurrence_form.html"

    def get_initial(self):
        # 지도나 목록에서 분류군을 고른 채 왔으면 그대로 채운다
        taxon = self.request.GET.get("taxon", "")
        return {"taxon": int(taxon)} if taxon.isdigit() else {}

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
        # 산출 입력 화면으로 돌아갈 때는 방금 만든 분류군을 골라 둔다. 다른 물음표는 버린다
        if url.split("?")[0] == reverse("occurrences:create"):
            return f"{reverse('occurrences:create')}?taxon={self.object.pk}"
        return url
