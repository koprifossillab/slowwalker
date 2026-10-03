# 할 일

- 산출을 CSV 로 한꺼번에 받아들이기 (Darwin Core 칸 이름 그대로)
- 자료가 많아지면 범위(bbox) 질의·쪽 나누기로 지도 전송량을 줄이기
- 3D 지형·지구본 보기 — 지금의 채집 자료 API를 공유하기
- 환경값의 출처·해상도·기간·수심을 보존하는 자료 구조와 환경 레이어
- 환경값 추출·조사 편향 처리·공간 분리 검증 후 서식 적합도 분석
- 배포(Dockerfile·compose) — GSM `deploy/` 를 본뜬다. 사진(`MEDIA_ROOT`)은 nginx 가 곧장 내주고 `slowwalkerweb/urls.py` 의 media 줄을 뺀다, 볼륨으로 둔다
- 라이선스 정하기
- 사진 백업 — DB 와 `web/media/` 를 함께 떠야 맞는다
