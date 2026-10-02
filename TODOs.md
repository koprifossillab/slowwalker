# 할 일

- 산출을 CSV 로 한꺼번에 받아들이기 (Darwin Core 칸 이름 그대로)
- 지도에서 분류군으로 거르기 (서버는 `?taxon=` 을 이미 받는다)
- 점이 많아지면 묶어 그리기(cluster) 또는 범위(bbox)로 자르기
- 배포(Dockerfile·compose) — GSM `deploy/` 를 본뜬다. 사진(`MEDIA_ROOT`)은 nginx 가 곧장 내주고 `slowwalkerweb/urls.py` 의 media 줄을 뺀다, 볼륨으로 둔다
- 라이선스 정하기
- 사진 백업 — DB 와 `web/media/` 를 함께 떠야 맞는다
