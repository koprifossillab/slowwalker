// 세계지도 위에 완보동물 산출 점을 그린다. 점은 서버의 GeoJSON 에서 한 번에 받는다.
(function () {
  "use strict";

  const mapEl = document.getElementById("map");
  const popupEl = document.getElementById("popup");
  const hoverEl = document.getElementById("hover");
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
  // 커서를 올린 점의 작은 카드. 마우스를 막지 않게(`stopEvent: false`, CSS 의 pointer-events) 띄운다
  const hover = new ol.Overlay({ element: hoverEl, stopEvent: false, offset: [14, 14], positioning: "top-left" });

  // 배경지도는 basemaps.js 가 안다. 여기서는 고르개와 잇기만 한다
  const basemapLayer = slowwalkerBasemaps.layer();
  const basemapEl = document.getElementById("basemap");
  basemapEl.value = slowwalkerBasemaps.remembered();
  basemapEl.addEventListener("change", () => {
    slowwalkerBasemaps.remember(basemapLayer.choose(basemapEl.value));
  });

  const map = new ol.Map({
    target: mapEl,
    layers: [
      basemapLayer,
      new ol.layer.Vector({ source, style: pointStyle }),
    ],
    overlays: [popup, hover],
    view: new ol.View({ center: [0, 2000000], zoom: 2, minZoom: 1 }),
  });

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function row(label, value) {
    return value ? `<dt>${label}</dt><dd>${esc(value)}</dd>` : "";
  }

  function detailUrl(feature) {
    // 자세히 화면의 주소는 템플릿이 0 자리로 알려 준다(`data-detail`)
    return mapEl.dataset.detail.replace("/0/", `/${feature.getId()}/`);
  }

  function photoCount(p) {
    return p.photo_count > 1 ? `<span class="n">사진 ${p.photo_count}장</span>` : "";
  }

  let shown = null;   // 팝업이 열려 있는 점

  map.on("singleclick", (evt) => {
    const feature = map.forEachFeatureAtPixel(evt.pixel, (f) => f, { hitTolerance: 4 });
    if (!feature) {
      popupEl.hidden = true;
      shown = null;
      return;
    }
    shown = feature;
    hoverEl.hidden = true;
    const p = feature.getProperties();
    popupEl.innerHTML = (p.photo
        ? `<a class="photo" href="${esc(detailUrl(feature))}"><img src="${esc(p.photo)}" alt="">${photoCount(p)}</a>` : "")
      + `<h2>${esc(p.taxon)}</h2><dl>`
      + row("나라", p.country) + row("산지", p.locality) + row("서식지", p.habitat)
      + row("채집일", p.event_date) + row("근거", p.basis_of_record) + row("출처", p.reference)
      + "</dl>"
      + `<p class="more"><a href="${esc(detailUrl(feature))}">자세히 · 고치기</a></p>`;
    popupEl.hidden = false;
    popup.setPosition(feature.getGeometry().getCoordinates());
  });

  // 커서를 올리면 학명과 첫 사진을 작게 띄운다. 끌어서 옮기는 동안이나 팝업이 열린 점에서는 띄우지 않는다
  let hovered = null;
  map.on("pointermove", (evt) => {
    const feature = evt.dragging ? null
      : map.forEachFeatureAtPixel(evt.pixel, (f) => f, { hitTolerance: 4 });
    mapEl.style.cursor = feature ? "pointer" : "";
    if (!feature || feature === shown) {
      hoverEl.hidden = true;
      hovered = null;
      return;
    }
    if (feature !== hovered) {
      hovered = feature;
      const p = feature.getProperties();
      hoverEl.innerHTML = (p.photo ? `<img src="${esc(p.photo)}" alt="">` : "")
        + `<div class="cap"><i>${esc(p.taxon)}</i>${photoCount(p)}</div>`;
      hoverEl.classList.toggle("has-photo", Boolean(p.photo));
      hoverEl.hidden = false;
    }
    // 자리를 먼저 잡는다 — 자리가 없는 overlay 는 OpenLayers 가 숨겨 두어(display: none) 카드 크기가 0 으로 잰다
    hover.setPosition(evt.coordinate);
    // 지도 오른쪽·아래 끝 가까이에서는 카드를 커서의 반대쪽으로 뒤집는다 — 안 그러면 화면 밖으로 잘린다
    const [w, h] = map.getSize();
    const left = evt.pixel[0] > w - hoverEl.offsetWidth - 24;
    const up = evt.pixel[1] > h - hoverEl.offsetHeight - 24;
    hover.setPositioning(`${up ? "bottom" : "top"}-${left ? "right" : "left"}`);
    hover.setOffset([left ? -14 : 14, up ? -14 : 14]);
  });
  mapEl.addEventListener("pointerleave", () => { hoverEl.hidden = true; hovered = null; });
})();
