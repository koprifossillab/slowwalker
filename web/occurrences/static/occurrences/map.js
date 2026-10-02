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

  const map = new ol.Map({
    target: mapEl,
    layers: [
      new ol.layer.Tile({ source: new ol.source.OSM() }),
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
