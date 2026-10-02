# CLAUDE.md

완보동물(Tardigrada)의 산출(occurrence) 기록을 관리하고 세계지도 위에 보여 주는 웹 뷰어.
문서는 한국어로 쓴다 — 커밋 메시지, devlog, 주석 모두.

**뼈대와 규약은 GSM(`~/projects/GSM`)을 본떴다.** 자료·DB·배포는 나누지 않는다.
여기 적지 않은 규약(말을 고르는 규칙, 커밋·devlog 꼴)은 GSM 의 CLAUDE.md 를 따른다.

## 이름

저장소·DB(`slowwalker.db`)·Django 설정 패키지(`slowwalkerweb`)가 `slowwalker` 이다.
환경변수는 `SLOWWALKER_*`.

## 말

| 뜻 | 쓰는 말 | 쓰지 않는 말 |
|---|---|---|
| 한 분류군이 한 자리에서 나왔다는 기록 하나 | **산출**(`Occurrence`) | 출현, 발견, 마커 |
| 문·강·목·과·속·종 하나 | **분류군**(`Taxon`) | 종(종이 아닐 수도 있다) |
| 산출이 나온 곳의 이름 | **산지**(`locality`) | 장소, 위치 |
| 지도의 보이는 범위 | **범위**(bbox) | 영역, 뷰포트 |

칸 이름은 Darwin Core(GBIF)를 따른다 — `decimal_latitude`·`basis_of_record`·`recorded_by` 따위.
새 칸을 더할 때도 Darwin Core 에 맞는 말이 있으면 그것을 쓴다.

## 자료의 층

```
분류군   Taxon       parent 로 위아래를 잇는다
 └ 산출   Occurrence  위경도 하나 + 산지·서식지·채집일·출처
```

## 구조

```
web/slowwalkerweb/   Django 설정 (settings·urls·version)
web/occurrences/     앱 하나뿐이다
  models.py          분류군·산출
  views.py           지도 화면, 산출 GeoJSON, healthz
  static/occurrences/
    map.js           OpenLayers 로 점을 그린다
    vendor/          OpenLayers 9.2.4 (GSM 과 같은 파일)
  tests/
devlog/              판단과 근거
```

**공간 연산은 하지 않는다** — GeoDjango·GDAL 없이 위경도를 숫자 두 칸으로 둔다. 지도는 브라우저가 그린다.

## 판

`web/slowwalkerweb/version.py` 와 `CHANGELOG.md` 맨 위 판을 손으로 맞춘다.

## 커밋과 PR

GSM 과 같다 — 기능마다 `feature/<영어-kebab>` 브랜치, 메시지는 한국어로 무엇을 했는지 쓰고 끝에
devlog 를 붙인다(`(koprifossillab 001)`). `git add` 는 고친 파일만 지정한다.

## devlog

`devlog/YYYYMMDD_{author}_{nnn}_{title}.md`, 계획은 `..._P{nn}_...`. 머리줄 아래에
`날짜 · \`브랜치\` · 글쓴이`. **무엇을 했는지가 아니라 왜 그렇게 했고 무엇을 버렸는지를 적는다.**
새 파일은 [devlog/README.md](devlog/README.md) 색인에 한 줄 더한다.
