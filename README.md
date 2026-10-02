# slowwalker — 완보동물 산출 지도

완보동물(Tardigrada)의 산출(occurrence) 기록을 모아 세계지도 위에 점으로 보여 준다.

- Django 5.2 · SQLite · OpenLayers 9 (저장소에 담아 둔다, CDN 을 안 탄다)
- 배경지도는 EOX 타일(지형 음영·Sentinel-2 위성, 비상업 이용만) — OSM 은 연구소 IP 가 막힌 적이 있어 쓰지 않는다
- 기록은 Django 관리 화면(`/admin/`)에서 넣는다

## 돌리기

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env            # 필요하면 고친다
python web/manage.py migrate
python web/manage.py createsuperuser
python web/manage.py runserver
```

- 지도: <http://127.0.0.1:8000/>
- 관리: <http://127.0.0.1:8000/admin/>
- 산출 GeoJSON: <http://127.0.0.1:8000/occurrences.geojson> (`?taxon=<id>` 로 거른다)
- 상태: <http://127.0.0.1:8000/healthz/>

## 시험

```sh
python web/manage.py test occurrences
```

## 자료의 출처

- 배경지도 © EOX IT Services GmbH — Terrain Light(OpenStreetMap 자료 포함), Sentinel-2 cloudless 2023 (CC BY-NC-SA 4.0)
- OpenLayers (BSD-2) — `web/occurrences/static/occurrences/vendor/`
