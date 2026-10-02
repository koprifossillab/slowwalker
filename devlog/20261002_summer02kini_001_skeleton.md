# 뼈대를 GSM 꼴로 세운다

2026-10-02 · `main` · summer02kini

## 무엇을 본떴나

GSM 의 꼴을 그대로 가져왔다 — `web/` 아래 Django, 설정 패키지 `<이름>web`, 앱 하나, 저장소 뿌리의 `.env`
를 `_load_env()` 로 읽기(python-dotenv 없이), `URL_PREFIX` 를 `urls.py` 한 곳에서만 붙이기,
requirements 를 web/dev 로 가르기, whitenoise, OpenLayers 를 저장소에 담기, `version.py`·CHANGELOG.

## 왜 GeoDjango 가 아닌가

산출은 위경도 하나다. 지도는 브라우저가 그리고 서버는 GeoJSON 만 낸다 — 공간 질의가 없으므로 GDAL 을
들일 까닭이 없다. 범위로 자르기가 필요해져도 위경도 두 칸의 범위 비교로 된다(색인을 걸어 두었다).
거리·다각형 안에 드는지 같은 것이 필요해지면 그때 다시 따진다.

## 왜 Darwin Core 이름인가

완보동물 산출 자료의 큰 덩어리는 GBIF 에 있고, 논문 부록도 대개 Darwin Core 꼴이다. 칸 이름을 맞춰 두면
받고 내보낼 때 옮겨 적기만 하면 된다. 다만 Darwin Core 의 모든 칸을 다 두지는 않았다 — 쓰는 것만.

## 버린 것

- **Leaflet** — 더 가볍지만 GSM 과 같은 OpenLayers 를 쓰면 GSM 에서 쌓은 것(극 투영·레이어 손잡이)을 옮겨 올 수 있다.
- **산출에 분류군 이름을 글자로 두기** — 동물이름 표기가 제각각이라 같은 종이 여럿으로 갈린다. `Taxon` 을 따로 둔다.
- **라이선스** — GSM 은 AGPL-3.0 이지만 이것은 사람이 정한다. 아직 `LICENSE` 를 두지 않았다.
