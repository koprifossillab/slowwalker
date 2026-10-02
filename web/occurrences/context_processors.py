"""모든 화면의 머리줄이 쓰는 값."""
from django.conf import settings

from slowwalkerweb.version import VERSION


def site(request):
    return {"version": VERSION, "edit_requires_login": settings.EDIT_REQUIRES_LOGIN}
