// 산출 하나의 작은 지도.
//
// - 자세히 화면: `data-lat`·`data-lon` 의 점 하나를 보여 준다
// - 입력 화면: `data-lat-input`·`data-lon-input` 이 가리키는 칸과 잇는다. 지도를 누르면 칸이 채워지고,
//   칸에 숫자를 적으면 점이 따라간다
(function () {
  "use strict";

  const el = document.getElementById("minimap");
  if (!el) return;

  const latInput = el.dataset.latInput && document.getElementById(el.dataset.latInput);
  const lonInput = el.dataset.lonInput && document.getElementById(el.dataset.lonInput);
  const picking = Boolean(latInput && lonInput);
  const maxMapLatitude = 85.0511287798066;

  const point = new ol.Feature();
  const map = new ol.Map({
    target: el,
    layers: [
      slowwalkerBasemaps.layer(),
      new ol.layer.Vector({
        source: new ol.source.Vector({ features: [point] }),
        style: new ol.style.Style({
          image: new ol.style.Circle({
            radius: 7,
            fill: new ol.style.Fill({ color: "rgba(214, 90, 49, 0.9)" }),
            stroke: new ol.style.Stroke({ color: "#ffffff", width: 2 }),
          }),
        }),
      }),
    ],
    view: new ol.View({ center: [0, 2000000], zoom: 1, minZoom: 1 }),
  });

  // 극지 좌표를 지도 가장자리로 옮겨 보이지 않는다. 원래 좌표는 입력 칸과 기록에 남긴다.
  const projectionNote = document.createElement("div");
  projectionNote.setAttribute("role", "status");
  projectionNote.textContent = "위도 ±85.05°를 넘는 채집지는 이 2D 지도에 표시되지 않습니다. 기록의 위·경도는 그대로 보존됩니다.";
  projectionNote.hidden = true;
  Object.assign(projectionNote.style, {
    position: "absolute", left: "52px", right: "12px", top: "12px", zIndex: "2",
    padding: "10px 12px", borderRadius: "6px", background: "rgba(255,255,255,.96)",
    color: "#33424a", fontSize: "13px", lineHeight: "1.5", pointerEvents: "none",
  });
  el.style.position = "relative";
  el.appendChild(projectionNote);

  /** 위경도가 둘 다 맞는 숫자면 [경도, 위도], 아니면 null. */
  function lonLat(lat, lon) {
    lat = parseFloat(lat);
    lon = parseFloat(lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return [lon, lat];
  }

  function show(ll, zoomTo) {
    const outsideProjection = Boolean(ll && Math.abs(ll[1]) > maxMapLatitude);
    projectionNote.hidden = !outsideProjection;
    if (!ll || outsideProjection) {
      point.setGeometry(undefined);
      return;
    }
    const xy = ol.proj.fromLonLat(ll);
    point.setGeometry(new ol.geom.Point(xy));
    if (zoomTo) map.getView().animate({ center: xy, zoom: Math.max(map.getView().getZoom(), 5), duration: 0 });
  }

  if (!picking) {
    show(lonLat(el.dataset.lat, el.dataset.lon), true);
    return;
  }

  // 입력 화면 — 고칠 때는 있던 자리로 연다
  show(lonLat(latInput.value, lonInput.value), true);

  map.on("singleclick", (evt) => {
    const [lon, lat] = ol.proj.toLonLat(evt.coordinate);
    // 화면을 옆으로 돌리면 경도가 ±180 을 넘는다. 되감고, 모델처럼 소수 6 자리로 자른다
    const wrapped = (((lon + 180) % 360) + 360) % 360 - 180;
    latInput.value = lat.toFixed(6);
    lonInput.value = wrapped.toFixed(6);
    show([wrapped, lat], false);
  });

  for (const input of [latInput, lonInput]) {
    input.addEventListener("change", () => show(lonLat(latInput.value, lonInput.value), true));
  }
})();
