// 세계지도 위에 완보동물 산출 점을 그린다. 점은 서버의 GeoJSON 에서 한 번에 받는다.
(function () {
  "use strict";

  const mapEl = document.getElementById("map");
  const popupEl = document.getElementById("popup");
  const countEl = document.getElementById("count");

  const pointStyle = new ol.style.Style({
    image: new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color: "rgba(214, 90, 49, 0.85)" }),
      stroke: new ol.style.Stroke({ color: "#ffffff", width: 1.2 }),
    }),
  });

  const source = new ol.source.Vector({
    url: mapEl.dataset.geojson,
    format: new ol.format.GeoJSON({ featureProjection: "EPSG:3857" }),
  });
  source.on("featuresloadend", () => {
    countEl.textContent = `산출 ${source.getFeatures().length.toLocaleString("ko-KR")}건`;
  });
  source.on("featuresloaderror", () => { countEl.textContent = "산출을 못 받았다"; });

  const popup = new ol.Overlay({ element: popupEl, stopEvent: true });

  // 배경지도 — GSM 과 같이 EOX 타일을 브라우저가 곧장 부른다.
  // OpenStreetMap 은 쓰지 않는다. 연구소 망의 바깥 IP 가 OSM 정책 위반으로 막힌 적이 있다(GSM devlog 003).
  // EOX 는 열쇠가 없고 CORS 를 열어 두었지만 비상업 이용만 된다(CC BY-NC-SA 4.0).
  const EOX_S2 = 'Sentinel-2 cloudless by <a href="https://s2maps.eu" target="_blank" rel="noopener">EOX IT Services GmbH</a> (contains modified Copernicus Sentinel data 2023, CC BY-NC-SA 4.0)';
  const EOX_TERRAIN = 'Terrain Light © <a href="https://maps.eox.at" target="_blank" rel="noopener">EOX IT Services GmbH</a>, data © OpenStreetMap contributors and others (CC BY-NC-SA 4.0)';

  function eoxSource(name, maxZoom, attribution) {
    return new ol.source.XYZ({
      // WMTS 의 자리 차례가 z/y/x 다
      url: `https://tiles.maps.eox.at/wmts/1.0.0/${name}/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg`,
      crossOrigin: "anonymous",
      maxZoom,
      attributions: attribution,
    });
  }

  const BASEMAPS = {
    eox_terrain: () => eoxSource("terrain-light_3857", 13, EOX_TERRAIN),
    eox_s2: () => eoxSource("s2cloudless-2023_3857", 16, EOX_S2),
    none: () => null,
  };

  const basemapLayer = new ol.layer.Tile();
  const basemapEl = document.getElementById("basemap");

  // 고른 배경은 이 브라우저에만 기억한다. 저장소를 못 쓰면 기본값으로 돈다
  function remembered() {
    try { return localStorage.getItem("slowwalker.basemap"); } catch (e) { return null; }
  }
  function setBasemap(key) {
    if (!(key in BASEMAPS)) key = "eox_terrain";
    basemapLayer.setSource(BASEMAPS[key]());
    basemapEl.value = key;
    try { localStorage.setItem("slowwalker.basemap", key); } catch (e) { /* 기억 못 해도 된다 */ }
  }
  setBasemap(remembered());
  basemapEl.addEventListener("change", () => setBasemap(basemapEl.value));

  const map = new ol.Map({
    target: mapEl,
    layers: [
      basemapLayer,
      new ol.layer.Vector({ source, style: pointStyle }),
    ],
    overlays: [popup],
    view: new ol.View({ center: [0, 2000000], zoom: 2, minZoom: 1 }),
  });

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function row(label, value) {
    return value ? `<dt>${label}</dt><dd>${esc(value)}</dd>` : "";
  }

  map.on("singleclick", (evt) => {
    const feature = map.forEachFeatureAtPixel(evt.pixel, (f) => f, { hitTolerance: 4 });
    if (!feature) {
      popupEl.hidden = true;
      return;
    }
    const p = feature.getProperties();
    popupEl.innerHTML = `<h2>${esc(p.taxon)}</h2><dl>`
      + row("나라", p.country) + row("산지", p.locality) + row("서식지", p.habitat)
      + row("채집일", p.event_date) + row("근거", p.basis_of_record) + row("출처", p.reference)
      + "</dl>";
    popupEl.hidden = false;
    popup.setPosition(feature.getGeometry().getCoordinates());
  });

  map.on("pointermove", (evt) => {
    mapEl.style.cursor = map.hasFeatureAtPixel(evt.pixel, { hitTolerance: 4 }) ? "pointer" : "";
  });
})();
