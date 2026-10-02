// 배경지도 — 세계지도(map.js)와 자세히·입력 화면의 작은 지도(pickmap.js)가 함께 쓴다.
//
// GSM 과 같이 EOX 타일을 브라우저가 곧장 부른다.
// OpenStreetMap 은 쓰지 않는다. 연구소 망의 바깥 IP 가 OSM 정책 위반으로 막힌 적이 있다(GSM devlog 003).
// EOX 는 열쇠가 없고 CORS 를 열어 두었지만 비상업 이용만 된다(CC BY-NC-SA 4.0).
window.slowwalkerBasemaps = (function () {
  "use strict";

  const EOX_S2 = 'Sentinel-2 cloudless by <a href="https://s2maps.eu" target="_blank" rel="noopener">EOX IT Services GmbH</a> (contains modified Copernicus Sentinel data 2023, CC BY-NC-SA 4.0)';
  const EOX_TERRAIN = 'Terrain Light © <a href="https://maps.eox.at" target="_blank" rel="noopener">EOX IT Services GmbH</a>, data © OpenStreetMap contributors and others (CC BY-NC-SA 4.0)';
  const STORE_KEY = "slowwalker.basemap";
  const DEFAULT = "eox_terrain";

  function eoxSource(name, maxZoom, attribution) {
    return new ol.source.XYZ({
      // WMTS 의 자리 차례가 z/y/x 다
      url: `https://tiles.maps.eox.at/wmts/1.0.0/${name}/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg`,
      crossOrigin: "anonymous",
      maxZoom,
      attributions: attribution,
    });
  }

  const SOURCES = {
    eox_terrain: () => eoxSource("terrain-light_3857", 13, EOX_TERRAIN),
    eox_s2: () => eoxSource("s2cloudless-2023_3857", 16, EOX_S2),
    none: () => null,
  };

  // 고른 배경은 이 브라우저에만 기억한다. 저장소를 못 쓰면 기본값으로 돈다
  function remembered() {
    let key = null;
    try { key = localStorage.getItem(STORE_KEY); } catch (e) { /* 기억 못 해도 된다 */ }
    return key in SOURCES ? key : DEFAULT;
  }

  function remember(key) {
    try { localStorage.setItem(STORE_KEY, key); } catch (e) { /* 기억 못 해도 된다 */ }
  }

  /** 배경 레이어 하나. `choose(key)` 로 바꾼다. 처음엔 이 브라우저가 마지막으로 고른 것.
   *  (`set` 이라 부르면 안 된다 — OpenLayers 가 속성을 적는 제 `set` 을 덮어 지도가 통째로 멈춘다) */
  function layer() {
    const tile = new ol.layer.Tile();
    tile.choose = function (key) {
      if (!(key in SOURCES)) key = DEFAULT;
      tile.setSource(SOURCES[key]());
      return key;
    };
    tile.choose(remembered());
    return tile;
  }

  return { layer, remembered, remember };
})();
