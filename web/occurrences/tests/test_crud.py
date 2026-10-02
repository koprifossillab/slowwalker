"""산출을 넣고·보고·고치고·지우는 화면."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from occurrences.models import Occurrence, Taxon


def form_data(taxon, **over):
    data = {
        "taxon": taxon.pk, "basis_of_record": "PreservedSpecimen",
        "decimal_latitude": "37.566500", "decimal_longitude": "126.978000",
        "coordinate_uncertainty_m": "", "country": "대한민국", "locality": "서울 남산",
        "habitat": "이끼", "elevation_m": "", "event_date": "2026-05-01", "recorded_by": "",
        "reference": "", "remarks": "",
    }
    # 고치기 화면은 사진 줄(formset)의 management form 도 보낸다. 브라우저는 늘 보낸다
    data.update({"photos-TOTAL_FORMS": 0, "photos-INITIAL_FORMS": 0,
                 "photos-MIN_NUM_FORMS": 0, "photos-MAX_NUM_FORMS": 1000})
    data.update(over)
    return data


class Crud(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.milnesium = Taxon.objects.create(scientific_name="Milnesium tardigradum", authorship="Doyère, 1840")
        cls.echiniscus = Taxon.objects.create(scientific_name="Echiniscus testudo")
        cls.sejong = Occurrence.objects.create(
            taxon=cls.milnesium, decimal_latitude="-62.223000", decimal_longitude="-58.786000",
            country="남극", locality="세종기지", event_date=date(2025, 1, 15))

    def test_목록과_자세히는_누구나_본다(self):
        res = self.client.get(reverse("occurrences:list"))
        self.assertContains(res, "Milnesium tardigradum")
        res = self.client.get(reverse("occurrences:detail", args=[self.sejong.pk]))
        self.assertContains(res, "세종기지")
        self.assertContains(res, 'data-lat="-62.223000"')

    def test_목록은_말로_찾고_분류군으로_거른다(self):
        Occurrence.objects.create(taxon=self.echiniscus, decimal_latitude=1, decimal_longitude=2, locality="한라산")
        res = self.client.get(reverse("occurrences:list"), {"q": "한라"})
        self.assertEqual([o.locality for o in res.context["object_list"]], ["한라산"])
        res = self.client.get(reverse("occurrences:list"), {"taxon": self.milnesium.pk})
        self.assertEqual([o.pk for o in res.context["object_list"]], [self.sejong.pk])

    def test_넣는다(self):
        res = self.client.post(reverse("occurrences:create"), form_data(self.echiniscus))
        made = Occurrence.objects.get(locality="서울 남산")
        self.assertRedirects(res, reverse("occurrences:detail", args=[made.pk]))
        self.assertEqual(made.decimal_latitude, Decimal("37.566500"))
        self.assertEqual(made.event_date, date(2026, 5, 1))

    def test_위도가_범위를_넘으면_받지_않는다(self):
        res = self.client.post(reverse("occurrences:create"), form_data(self.echiniscus, decimal_latitude="91"))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["form"].errors["decimal_latitude"])
        self.assertFalse(Occurrence.objects.filter(locality="서울 남산").exists())

    def test_고친다(self):
        res = self.client.post(reverse("occurrences:update", args=[self.sejong.pk]),
                               form_data(self.milnesium, locality="세종기지 앞 이끼밭"))
        self.assertRedirects(res, reverse("occurrences:detail", args=[self.sejong.pk]))
        self.sejong.refresh_from_db()
        self.assertEqual(self.sejong.locality, "세종기지 앞 이끼밭")

    def test_지운다_분류군은_남는다(self):
        res = self.client.get(reverse("occurrences:delete", args=[self.sejong.pk]))
        self.assertContains(res, "지울까")
        res = self.client.post(reverse("occurrences:delete", args=[self.sejong.pk]))
        self.assertRedirects(res, reverse("occurrences:list"))
        self.assertFalse(Occurrence.objects.filter(pk=self.sejong.pk).exists())
        self.assertTrue(Taxon.objects.filter(pk=self.milnesium.pk).exists())

    def test_분류군을_더하면_고른_채로_입력_화면에_돌아간다(self):
        res = self.client.post(reverse("occurrences:taxon_create"), {
            "scientific_name": "Ramazzottius varieornatus", "authorship": "Bertolani & Kinchin, 1993",
            "rank": "species", "parent": "", "next": reverse("occurrences:create"),
        })
        made = Taxon.objects.get(scientific_name="Ramazzottius varieornatus")
        self.assertRedirects(res, f"{reverse('occurrences:create')}?taxon={made.pk}")
        res = self.client.get(res.url)
        self.assertEqual(res.context["form"].initial["taxon"], made.pk)

    def test_분류군_뒤에_바깥_주소로는_보내지_않는다(self):
        res = self.client.post(reverse("occurrences:taxon_create"), {
            "scientific_name": "Hypsibius exemplaris", "rank": "species", "next": "https://example.com/",
        })
        made = Taxon.objects.get(scientific_name="Hypsibius exemplaris")
        self.assertRedirects(res, f"{reverse('occurrences:create')}?taxon={made.pk}")


class EditLogin(TestCase):
    """`EDIT_REQUIRES_LOGIN` — 연구소 안 시험 동안은 끄고(기본), 켜면 넣기·고치기·지우기에 로그인을 묻는다."""

    @classmethod
    def setUpTestData(cls):
        cls.taxon = Taxon.objects.create(scientific_name="Milnesium tardigradum")
        cls.occ = Occurrence.objects.create(taxon=cls.taxon, decimal_latitude=0, decimal_longitude=0)

    def test_기본은_로그인_없이_고친다(self):
        for name, args in (("create", []), ("update", [self.occ.pk]), ("delete", [self.occ.pk]),
                           ("taxon_create", [])):
            res = self.client.get(reverse(f"occurrences:{name}", args=args))
            self.assertEqual(res.status_code, 200, name)

    @override_settings(EDIT_REQUIRES_LOGIN=True)
    def test_켜면_로그인으로_보낸다(self):
        res = self.client.get(reverse("occurrences:update", args=[self.occ.pk]))
        self.assertRedirects(res, f"{reverse('login')}?next={reverse('occurrences:update', args=[self.occ.pk])}")
        # 보기는 그대로 열려 있다
        self.assertEqual(self.client.get(reverse("occurrences:detail", args=[self.occ.pk])).status_code, 200)

    @override_settings(EDIT_REQUIRES_LOGIN=True)
    def test_켜도_로그인하면_고친다(self):
        self.client.force_login(User.objects.create_user("tester"))
        res = self.client.post(reverse("occurrences:delete", args=[self.occ.pk]))
        self.assertRedirects(res, reverse("occurrences:list"))
