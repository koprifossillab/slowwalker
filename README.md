# slowwalker — 완보동물 산출 지도

완보동물(Tardigrada)의 채집지·시료·산출(occurrence) 기록을 세계지도에서 함께 읽는다.

처음에는 웃으며 앞다리를 흔드는 완보동물이 잠깐 인사한 뒤 2D 지도를 연다. `지도로 바로가기`로
건너뛰거나 `인사 더 보기`로 머무를 수 있으며, 지도 아래의 `인사 다시 보기`로 다시 연다.
왼쪽에서 채집지를 찾고, 지도 위 점을 누르면 오른쪽에서
채집 날짜·채집자 → 시료 번호·기질 생물 → 완보동물 학명과 사진을 따라간다.
`지도에 채집지 추가`로 지도에서 자리를 고르거나 `좌표 직접 입력`에서 좌표를 적는다.

## 자료를 넣는 순서

1. 채집지의 이름·위경도·산지·해양/육상/담수 구분과 사진을 넣는다.
2. 채집지에 날짜·채집자·방법·노력량을 적은 채집 기록을 더한다. 같은 곳의 반복 채집은 새 채집으로 넣는다.
3. 채집에 시료 번호·기질·따개비 등 기질 생물의 학명과 시료 사진을 붙인다.
4. 시료에서 나온 완보동물을 산출로 더한다. 개체 수·동정자·학명·사진을 기록한다.

기존의 시료 연결 없는 산출도 계속 쓸 수 있다. 기존 산출을 좌표만 보고 자동으로 묶지는 않는다.
연결한 산출의 산지·좌표·채집일·채집자는 채집지와 채집에서 읽는다. 산출의 독자적인 동정·문헌 근거는
별도로 남긴다. 정확한 연월일이 없는 문헌은 `채집일 원문`에 남기며 임의의 날짜를 만들지 않는다.

- Django 5.2 · SQLite · OpenLayers 9 (저장소에 담아 둔다, CDN 을 안 탄다) · Pillow(사진 섬네일)
- 배경지도는 EOX 타일(지형 음영·Sentinel-2 위성, 비상업 이용만) — OSM 은 연구소 IP 가 막힌 적이 있어 쓰지 않는다
- 산출은 전용 화면(`/occurrences/`)에서 넣고·고치고·지운다. 분류군의 계층과 계정은 관리 화면(`/admin/`)에서
- 채집지·시료·산출마다 사진을 여러 장 붙인다. 파일은 `web/media/`(`SLOWWALKER_MEDIA_DIR`)에 쌓이고 커밋하지 않는다 — DB와 함께 백업한다
- 고치는 데 로그인을 묻지 않는 것이 기본이다(연구소 안 시험용). `SLOWWALKER_EDIT_REQUIRES_LOGIN=1` 이면 묻는다

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
- 산출 목록·입력: <http://127.0.0.1:8000/occurrences/> · <http://127.0.0.1:8000/occurrences/new/>
- 관리: <http://127.0.0.1:8000/admin/>
- 산출 GeoJSON: <http://127.0.0.1:8000/occurrences.geojson> (`?taxon=<id>` 로 거른다)
- 채집지 및 단독 산출 지도 자료: <http://127.0.0.1:8000/map-data.geojson>
- 상태: <http://127.0.0.1:8000/healthz/>

검토용 가상 자료를 쓸 때는 별도 DB/사진 폴더를 지정하고 `SLOWWALKER_PREVIEW_NOTICE="미리보기 · 예시 자료"`를
설정해 실제 자료와 구별한다. 이 표시는 기본값에서 나타나지 않는다.
2D 지도 투영의 한계로 극점 근처(위도 약 ±85.05° 바깥)의 기록은 목록과 상세 정보에서 확인한다.
원본 좌표는 그대로 저장한다.

## 시험

```sh
python web/manage.py test occurrences
python web/manage.py makemigrations --check --dry-run
```

## 운영에 반영하기 전

DB와 사진을 같은 시점의 백업으로 보관하고, 별도 DB에서 마이그레이션과 사진 표시를 검증한다.
0.4의 새 채집/시료 연결과 사진을 넣은 뒤에는 `migrate 0002`만으로 0.3으로 돌아갈 수 없다.
되돌릴 때는 이전 코드와 함께 **마이그레이션 전 DB 및 사진 백업**을 복원해야 한다.
연구실의 기존 규약대로 검토 브랜치에서 PR을 만들며, main 병합은 사람이 결정한다.

## 다음 단계

- 3D 지형과 지구본: 같은 채집 자료 API를 쓰는 별도 보기. 현재 지형 음영 배경은 실제 3D가 아니다.
- 환경 자료: 해류·풍향·파랑·기온·수온·염도 등을 출처·단위·해상도·시기·수심과 함께 연결한다.
- 철새 경로: 이용 가능한 자료의 접근 조건과 시공간 범위를 확인한 뒤 겹쳐 본다.
- 분포 분석: 환경값 추출, 조사 편향과 공간 분리 검증을 먼저 마련하고 MaxEnt 등의 서식 적합도 분석을 붙인다.
  산출이 없다는 사실만으로 부재를 만들지 않으며, 변수 중요도를 인과관계나 이동 기작의 증명으로 표시하지 않는다.

필드 이름과 자료 구분은 [Darwin Core](https://dwc.tdwg.org/terms/)를 참고한다.
MaxEnt 결과 해석은 [공식 튜토리얼](https://biodiversityinformatics.amnh.org/open_source/maxent/Maxent_tutorial_2021.pdf)을 참고한다.

## 자료의 출처

- 배경지도 © EOX IT Services GmbH — Terrain Light(OpenStreetMap 자료 포함), Sentinel-2 cloudless 2023 (CC BY-NC-SA 4.0)
- OpenLayers (BSD-2) — `web/occurrences/static/occurrences/vendor/`
