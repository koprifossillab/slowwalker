/* 채집지 → 채집 사건 → 시료 → 산출 기록을 2D 지도와 연결한다. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const mapEl = $("map");
  const listEl = $("record-list");
  const statusEl = $("record-status");
  const detailEl = $("detail-content");
  const panelEl = $("detail-panel");
  const sidebarEl = $("sidebar");
  const STORE_KEY = "slowwalker.viewport.v1";
  const MAX_LAT = 85.05112878;
  const realmNames = { marine: "해양", terrestrial: "육상", freshwater: "담수", unknown: "환경 미지정" };
  const realmColors = { marine: "#397f9b", terrestrial: "#6d8663", freshwater: "#8874ab", unknown: "#b38152" };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const motion = reducedMotion ? 0 : 300;
  let allRecords = [];
  let visibleRecords = [];
  let currentRealm = "all";
  let selectedKey = null;
  let picking = false;
  let detailRequest = null;
  let detailSequence = 0;
  let noticeTimer = null;

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }
  function safeUrl(value, image = false) {
    if (!value) return "";
    try {
      const url = new URL(value, window.location.href);
      if (!["http:", "https:"].includes(url.protocol)) return "";
      if (!image && url.origin !== window.location.origin) return "";
      return esc(url.href);
    } catch (_) { return ""; }
  }
  function link(url, title, className = "") {
    const safe = safeUrl(url);
    return safe ? `<a href="${safe}"${className ? ` class="${className}"` : ""}>${esc(title)}</a>` : "";
  }
  function row(label, value) {
    return value !== null && value !== undefined && value !== ""
      ? `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>` : "";
  }
  function icon(name) { return `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`; }
  function realmOf(record) { return Object.hasOwn(realmNames, record.p.realm) ? record.p.realm : "unknown"; }
  function number(value) { return Math.max(0, Number(value) || 0); }
  function count(value) { return number(value).toLocaleString("ko-KR"); }
  function norm(text) { return String(text || "").normalize("NFKC").toLocaleLowerCase(); }
  function coordinateLabel(lon, lat) {
    return `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? "N" : "S"}  /  ${Math.abs(lon).toFixed(5)}° ${lon >= 0 ? "E" : "W"}`;
  }
  function normalizeLongitude(lon) { return ((lon + 180) % 360 + 360) % 360 - 180; }
  function notice(message, timeout = 5500) {
    clearTimeout(noticeTimer);
    $("map-notice").textContent = message;
    $("map-notice").hidden = !message;
    if (timeout) noticeTimer = setTimeout(() => { $("map-notice").hidden = true; }, timeout);
  }

  function rememberedView() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORE_KEY));
      if (stored && Array.isArray(stored.center) && stored.center.length === 2
          && stored.center.every(Number.isFinite) && Math.abs(stored.center[0]) <= 180
          && Math.abs(stored.center[1]) <= MAX_LAT && Number.isFinite(stored.zoom)
          && stored.zoom >= 1 && stored.zoom <= 18) return stored;
    } catch (_) { /* 시크릿 모드 등 저장소를 못 쓰는 환경에서도 지도를 연다. */ }
    return null;
  }
  const storedView = rememberedView();
  const view = new ol.View({
    center: ol.proj.fromLonLat(storedView ? storedView.center : [32, 18]),
    zoom: storedView ? storedView.zoom : 2.15,
    minZoom: 1,
    maxZoom: 18,
    enableRotation: false,
  });
  const source = new ol.source.Vector({ wrapX: true });
  const styleCache = new Map();
  function markerStyle(feature) {
    const records = feature.get("records");
    const active = records.some((record) => record.key === selectedKey);
    const sameRealm = records.every((record) => realmOf(record) === realmOf(records[0]));
    const realm = sameRealm ? realmOf(records[0]) : "unknown";
    const n = records.length;
    const key = `${realm}:${n}:${active}`;
    if (!styleCache.has(key)) {
      const radius = n > 1 ? 11 : 6;
      const styles = [];
      if (active) styles.push(new ol.style.Style({ image: new ol.style.Circle({
        radius: radius + 6,
        fill: new ol.style.Fill({ color: "rgba(207, 167, 96, 0.23)" }),
        stroke: new ol.style.Stroke({ color: "#b58b47", width: 1.3 }),
      }), zIndex: 20 }));
      styles.push(new ol.style.Style({
        image: new ol.style.Circle({ radius, fill: new ol.style.Fill({ color: realmColors[realm] }),
          stroke: new ol.style.Stroke({ color: "#fffcf5", width: active ? 2.5 : 1.7 }) }),
        text: n > 1 ? new ol.style.Text({ text: n > 99 ? "99+" : String(n),
          font: "600 10px system-ui, sans-serif", fill: new ol.style.Fill({ color: "#ffffff" }) }) : undefined,
        zIndex: active ? 21 : 1,
      }));
      styleCache.set(key, styles);
    }
    return styleCache.get(key);
  }
  const basemapLayer = slowwalkerBasemaps.layer();
  const pointLayer = new ol.layer.Vector({ source, style: markerStyle });
  const map = new ol.Map({
    target: mapEl,
    layers: [basemapLayer, pointLayer],
    controls: [new ol.control.Attribution({ collapsible: true, collapsed: false }), new ol.control.ScaleLine()],
    view,
  });
  let tileErrors = 0;
  let currentTileSource = null;
  function watchBasemap() {
    const tileSource = basemapLayer.getSource();
    currentTileSource = tileSource;
    tileErrors = 0;
    if (!tileSource) return;
    tileSource.on("tileloaderror", () => {
      if (currentTileSource !== tileSource) return;
      tileErrors += 1;
      if (tileErrors === 3) notice("배경지도를 불러오지 못했습니다. 배경지도를 바꾸거나 네트워크를 확인하세요.", 10000);
    });
  }
  watchBasemap();
  $("basemap").value = slowwalkerBasemaps.remembered();
  $("basemap").addEventListener("change", () => {
    slowwalkerBasemaps.remember(basemapLayer.choose($("basemap").value));
    watchBasemap();
  });
  map.on("moveend", () => {
    const center = ol.proj.toLonLat(view.getCenter());
    const bounded = [normalizeLongitude(center[0]), Math.max(-MAX_LAT, Math.min(MAX_LAT, center[1]))];
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ center: bounded, zoom: view.getZoom() })); } catch (_) { /* 저장할 수 없어도 지도를 사용한다. */ }
  });

  function toggleSidebar(open) {
    document.body.classList.toggle("sidebar-open", open);
    $("sidebar-open").setAttribute("aria-expanded", String(open));
    // 모바일에서 화면 밖으로 접은 탐색 도구는 탭 키로 선택되지 않게 한다.
    sidebarEl.inert = !open && window.matchMedia("(max-width: 760px)").matches;
  }
  toggleSidebar(false);
  window.addEventListener("resize", () => {
    toggleSidebar(document.body.classList.contains("sidebar-open"));
    map.updateSize();
  });
  $("sidebar-open").addEventListener("click", () => { toggleSidebar(true); $("record-search").focus(); });
  $("sidebar-close").addEventListener("click", () => { toggleSidebar(false); $("sidebar-open").focus(); });

  function rebuildMarkers() {
    const groups = new Map();
    visibleRecords.forEach((record) => {
      if (!record.projectable) return;
      const key = record.lonlat.join(",");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(record);
    });
    source.clear();
    source.addFeatures(Array.from(groups.values(), (records) => new ol.Feature({
      geometry: new ol.geom.Point(ol.proj.fromLonLat(records[0].lonlat)), records,
    })));
  }
  function updateActiveList() {
    for (const button of listEl.querySelectorAll("[data-record-key]")) {
      const active = button.dataset.recordKey === selectedKey;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    pointLayer.changed();
  }
  function recordMarkup(record) {
    const p = record.p;
    const realm = realmOf(record);
    const taxa = Array.isArray(p.taxa) ? p.taxa : [];
    const sub = [p.country, p.kind === "site" ? `채집 ${count(p.event_count)}회 · 산출 ${count(p.occurrence_count)}건` : "독립 산출 기록"].filter(Boolean).join(" · ");
    const species = taxa.slice(0, 2).join(" · ") + (taxa.length > 2 ? ` 외 ${taxa.length - 2}분류군` : "");
    return `<button type="button" class="record-item" data-record-key="${esc(record.key)}" aria-pressed="false">
      <span class="record-marker ${realm}">${icon("pin")}</span><span class="record-text"><strong>${esc(p.name || p.locality || "이름 없는 기록")}</strong>
      <small>${esc(sub)}</small>${species ? `<small class="record-taxa">${esc(species)}</small>` : ""}${record.projectable ? "" : '<small>극지 좌표 · 목록에서 확인</small>'}</span><span class="record-arrow" aria-hidden="true">›</span></button>`;
  }
  function applyFilters() {
    if (!panelEl.hidden && !selectedKey) closeDetail(false);
    const query = norm($("record-search").value.trim());
    const words = query.split(/\s+/).filter(Boolean);
    visibleRecords = allRecords.filter((record) => (currentRealm === "all" || realmOf(record) === currentRealm)
      && words.every((word) => record.search.includes(word)));
    if (selectedKey && !visibleRecords.some((record) => record.key === selectedKey)) closeDetail(false);
    rebuildMarkers();
    const sites = visibleRecords.filter((record) => record.p.kind === "site").length;
    const occurrences = visibleRecords.reduce((sum, record) => sum + number(record.p.occurrence_count ?? (record.p.kind === "occurrence" ? 1 : 0)), 0);
    const taxa = new Set(visibleRecords.flatMap((record) => record.p.taxa || []));
    $("site-count").textContent = count(sites);
    $("occurrence-count").textContent = count(occurrences);
    $("taxon-count").textContent = count(taxa.size);
    listEl.innerHTML = visibleRecords.map(recordMarkup).join("");
    statusEl.hidden = visibleRecords.length > 0;
    if (!allRecords.length) {
      statusEl.innerHTML = `${icon("pin")}<strong>아직 등록된 기록이 없습니다</strong><p>첫 채집지를 지도에 표시하고<br>채집·시료·완보동물 기록을 연결하세요.</p>`;
    } else if (!visibleRecords.length) {
      statusEl.innerHTML = '<strong>검색 결과가 없습니다</strong><p>검색어나 서식 환경을 바꿔 보세요.</p><button type="button" data-reset-filters>필터 초기화</button>';
    }
    const polar = visibleRecords.filter((record) => !record.projectable).length;
    const legacy = visibleRecords.filter((record) => record.p.kind === "occurrence").length;
    $("list-footer").hidden = !polar && !legacy;
    $("list-footer").textContent = [legacy ? `독립 산출 기록 ${count(legacy)}건 포함` : "", polar ? `극지 ${count(polar)}건은 목록에서 확인` : ""].filter(Boolean).join(" · ");
    updateActiveList();
  }
  function resetFilters() {
    $("record-search").value = "";
    setRealm("all");
  }
  function setRealm(realm) {
    currentRealm = realm;
    for (const button of document.querySelectorAll(".realm-filter")) {
      const active = button.dataset.realm === realm;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    applyFilters();
  }
  document.querySelectorAll(".realm-filter").forEach((button) => button.addEventListener("click", () => setRealm(button.dataset.realm)));
  $("record-search").addEventListener("input", applyFilters);
  statusEl.addEventListener("click", (event) => {
    if (event.target.closest("[data-retry-records]")) loadRecords();
    if (event.target.closest("[data-reset-filters]")) resetFilters();
  });
  listEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-record-key]");
    if (!button) return;
    const record = visibleRecords.find((item) => item.key === button.dataset.recordKey);
    if (record) selectRecord(record, true);
  });

  async function loadRecords() {
    statusEl.hidden = false;
    statusEl.textContent = "기록을 불러오고 있습니다…";
    let startupOk = false;
    try {
      const response = await fetch(mapEl.dataset.geojson, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) throw new Error("Invalid map data");
      allRecords = data.features.map((feature) => {
        const coords = feature.geometry?.coordinates;
        if (feature.geometry?.type !== "Point" || !Array.isArray(coords) || coords.length < 2
            || !coords.slice(0, 2).every(Number.isFinite) || Math.abs(coords[0]) > 180 || Math.abs(coords[1]) > 90) return null;
        const p = feature.properties || {};
        const key = String(feature.id ?? `${p.kind}:${p.id}`);
        return { key, p, lonlat: coords.slice(0, 2), projectable: Math.abs(coords[1]) <= MAX_LAT,
          search: norm([p.name, p.locality, p.country, p.habitat, ...(p.taxa || [])].join(" ")) };
      }).filter(Boolean);
      applyFilters();
      const requestedSite = new URLSearchParams(window.location.search).get("site");
      if (requestedSite && /^\d+$/.test(requestedSite)) {
        const record = allRecords.find((item) => item.p.kind === "site" && String(item.p.id) === requestedSite);
        if (record) selectRecord(record, true);
      }
      if (allRecords.length < data.features.length) notice("좌표가 올바르지 않은 일부 기록을 지도에서 제외했습니다. 산출 목록에서 확인하세요.", 10000);
      startupOk = true;
    } catch (_) {
      allRecords = [];
      visibleRecords = [];
      source.clear();
      listEl.replaceChildren();
      for (const id of ["site-count", "occurrence-count", "taxon-count"]) $(id).textContent = "—";
      statusEl.innerHTML = '<strong>기록을 불러오지 못했습니다</strong><p>서버 연결을 확인하고 다시 시도하세요.</p><button type="button" data-retry-records>다시 불러오기</button>';
    } finally {
      // 원격 배경 타일 전체를 기다리지 않는다. 오류일 때도 재시도 화면에 들어갈 수 있게 한다.
      document.dispatchEvent(new CustomEvent("slowwalker:startup-settled", { detail: { ok: startupOk } }));
    }
  }

  function photosMarkup(photos, fallbackAlt) {
    if (!Array.isArray(photos) || !photos.length) return "";
    const valid = photos.filter((photo) => safeUrl(photo.url, true));
    if (!valid.length) return "";
    return `<div class="photo-strip${valid.length === 1 ? " single" : ""}">${valid.map((photo) => {
      const url = safeUrl(photo.url, true);
      const thumbnail = safeUrl(photo.thumbnail || photo.url, true);
      const caption = [photo.description, photo.creator ? `사진: ${photo.creator}` : "", photo.license].filter(Boolean).join(" · ");
      return `<figure><a href="${url}" target="_blank" rel="noopener"><img src="${thumbnail}" alt="${esc(photo.description || fallbackAlt)}" loading="lazy"></a>${caption ? `<figcaption>${esc(caption)}</figcaption>` : ""}</figure>`;
    }).join("")}</div>`;
  }
  function occurrenceMarkup(occurrence) {
    return `<div class="species-row">${link(occurrence.detail_url, occurrence.taxon || "미동정 분류군")}
      ${occurrence.individual_count != null ? `<span>${count(occurrence.individual_count)}개체</span>` : '<span>개체 수 미기록</span>'}
      ${occurrence.identification_qualifier ? `<p class="species-meta">동정 한정어 · ${esc(occurrence.identification_qualifier)}</p>` : ""}
      ${occurrence.identified_by ? `<p class="species-meta">동정자 · ${esc(occurrence.identified_by)}</p>` : ""}
      ${occurrence.basis_of_record ? `<p class="species-meta">기록 근거 · ${esc(occurrence.basis_of_record)}</p>` : ""}
      ${occurrence.reference ? `<p class="species-meta">출처 · ${esc(occurrence.reference)}</p>` : ""}
      ${occurrence.remarks ? `<p class="species-meta">비고 · ${esc(occurrence.remarks)}</p>` : ""}
      ${photosMarkup(occurrence.photos, occurrence.taxon || "완보동물 사진")}</div>`;
  }
  function sampleMarkup(sample) {
    const occurrences = sample.occurrences || [];
    return `<section class="sample-card"><h4>${esc(sample.sample_code || `시료 #${sample.id}`)}</h4>
      ${sample.substrate ? `<p class="sample-info">기질 · ${esc(sample.substrate)}</p>` : ""}
      ${sample.host_taxon ? `<p class="sample-info">숙주 분류군 · <i>${esc(sample.host_taxon)}</i></p>` : ""}
      ${sample.description ? `<p class="sample-info">${esc(sample.description)}</p>` : ""}
      ${photosMarkup(sample.photos, `${sample.sample_code || "시료"} 사진`)}
      <div class="event-links">${link(sample.edit_url, "시료 수정")}${link(sample.occurrence_create_url, "+ 완보동물 산출 추가")}</div>
      ${occurrences.length ? occurrences.map(occurrenceMarkup).join("") : '<p class="sample-info">등록된 산출 기록이 없습니다.</p>'}</section>`;
  }
  function eventMarkup(event, index) {
    const samples = event.samples || [];
    const date = event.event_date || event.event_date_verbatim || "채집일 미기록";
    return `<details class="collection-event"${index === 0 ? " open" : ""}><summary>${icon("calendar")}<span>${esc(date)}<small>${esc(event.recorded_by || "채집자 미기록")} · 시료 ${count(samples.length)}개</small></span></summary>
      <div class="event-body"><dl class="detail-fields">${row("채집자", event.recorded_by)}
      ${event.event_date && event.event_date_verbatim ? row("원문 채집일", event.event_date_verbatim) : ""}
      ${row("채집 방법", event.sampling_protocol)}${row("채집 노력", event.sampling_effort)}${row("출처", event.reference)}${row("비고", event.remarks)}</dl>
      <div class="event-links">${link(event.edit_url, "채집 정보 수정")}${link(event.sample_create_url, "+ 시료 추가")}</div>
      ${samples.length ? samples.map(sampleMarkup).join("") : '<p class="sample-info">이 채집에 시료를 추가해 주세요.</p>'}</div></details>`;
  }
  function renderDetail(data, record) {
    const p = record.p;
    const realm = realmOf(record);
    const isSite = p.kind === "site";
    const lon = Number(data.longitude ?? record.lonlat[0]);
    const lat = Number(data.latitude ?? record.lonlat[1]);
    let html = `<div class="detail-eyebrow"><span class="realm-dot ${realm}"></span>${esc(realmNames[realm])} · ${isSite ? "COLLECTION SITE" : "OCCURRENCE"}</div>
      <h2>${esc(data.name || data.taxon || p.name)}</h2>
      <p class="detail-place">${esc([data.country, data.locality].filter(Boolean).join(" · "))}</p>
      <div class="detail-coords">${esc(coordinateLabel(lon, lat))}</div>`;
    if (!record.projectable) html += '<p class="detail-empty">이 극지 좌표는 현재 배경지도의 표시 범위(남·북위 약 85°) 밖에 있습니다. 원래 좌표는 그대로 보존됩니다.</p>';
    html += photosMarkup(data.photos, isSite ? "채집지 사진" : (data.taxon || "산출 사진"));
    if (isSite) {
      const events = data.events || [];
      const samples = events.flatMap((event) => event.samples || []);
      const occurrences = samples.flatMap((sample) => sample.occurrences || []);
      html += `<div class="detail-metrics"><span><strong>${count(events.length)}</strong>채집</span><span><strong>${count(samples.length)}</strong>시료</span><span><strong>${count(occurrences.length)}</strong>산출 기록</span></div>
        <dl class="detail-fields">${row("서식지", data.habitat)}${row("좌표 불확도", data.coordinate_uncertainty_m != null ? `${data.coordinate_uncertainty_m} m` : null)}${row("비고", data.remarks)}</dl>
        <div class="detail-actions">${link(data.event_create_url, "+ 채집 기록 추가")}${link(data.edit_url, "채집지 수정")}${link(data.detail_url, "전체 정보 ↗")}</div>
        <h3 class="detail-section-title">채집 · 시료 · 완보동물 <span>${count(events.length)}회</span></h3>
        ${events.length ? events.map(eventMarkup).join("") : '<div class="detail-empty"><strong>첫 채집 기록을 연결하세요</strong>채집 날짜와 채집자를 기록한 뒤<br>시료와 산출 완보동물을 추가할 수 있습니다.</div>'}`;
    } else {
      html += `<dl class="detail-fields">${row("학명", data.taxon)}${row("서식지", data.habitat)}${row("채집일", data.event_date || data.event_date_verbatim)}${row("채집자", data.recorded_by)}
        ${row("개체 수", data.individual_count)}${row("동정자", data.identified_by)}${row("동정 한정어", data.identification_qualifier)}${row("기록 근거", data.basis_of_record)}${row("좌표 불확도", data.coordinate_uncertainty_m != null ? `${data.coordinate_uncertainty_m} m` : null)}${row("출처", data.reference)}${row("비고", data.remarks)}</dl>
        <div class="detail-actions">${link(data.detail_url, "전체 정보 · 사진 ↗")}${link(data.edit_url, "산출 기록 수정")}</div>
        <p class="detail-empty">채집지·시료에 아직 연결되지 않은 독립 산출 기록입니다.</p>`;
    }
    detailEl.innerHTML = html;
    detailEl.scrollTop = 0;
  }
  function openDetail(kind) {
    panelEl.hidden = false;
    document.body.classList.add("drawer-open");
    $("detail-kind").textContent = kind;
    toggleSidebar(false);
    $("coordinate-panel").hidden = true;
    $("coordinate-toggle").setAttribute("aria-expanded", "false");
  }
  function closeDetail(focusMap = true) {
    if (detailRequest) detailRequest.abort();
    detailSequence += 1;
    panelEl.hidden = true;
    document.body.classList.remove("drawer-open");
    selectedKey = null;
    updateActiveList();
    if (focusMap) mapEl.focus({ preventScroll: true });
  }
  async function selectRecord(record, pan) {
    setPicking(false);
    selectedKey = record.key;
    updateActiveList();
    openDetail(record.p.kind === "site" ? "채집지 상세" : "산출 기록 상세");
    detailEl.innerHTML = `<h2>${esc(record.p.name)}</h2><p class="detail-empty">상세 기록을 불러오고 있습니다…</p>`;
    if (pan && record.projectable) {
      const point = ol.proj.fromLonLat(record.lonlat);
      const targetZoom = Math.max(view.getZoom(), 7);
      // 상세 패널에 가려지지 않도록 선택한 점을 남은 지도 영역의 가운데에 둔다.
      const resolution = view.getResolutionForZoom(targetZoom);
      const desktopOffset = window.matchMedia("(min-width: 761px)").matches ? panelEl.offsetWidth / 2 : 0;
      view.animate({ center: [point[0] + desktopOffset * resolution, point[1]], zoom: targetZoom, duration: motion });
    }
    if (detailRequest) detailRequest.abort();
    detailRequest = new AbortController();
    const sequence = ++detailSequence;
    try {
      const url = safeUrl(record.p.data_url);
      if (!url) throw new Error("Missing detail URL");
      // 서버가 만든 동일 출처 URL임을 검사했다. HTML 이스케이프는 요청 주소에 적용하지 않는다.
      const response = await fetch(record.p.data_url, { signal: detailRequest.signal, credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (sequence !== detailSequence) return;
      renderDetail(data, record);
    } catch (error) {
      if (error.name === "AbortError" || sequence !== detailSequence) return;
      detailEl.innerHTML = `<h2>${esc(record.p.name)}</h2><div class="detail-empty"><strong>상세 정보를 불러오지 못했습니다</strong>서버 연결을 확인한 뒤 다시 시도하세요.<div class="detail-actions"><button type="button" class="button secondary" data-retry-detail>다시 시도</button>${link(record.p.detail_url, "전체 정보 열기")}</div></div>`;
    }
  }
  detailEl.addEventListener("click", (event) => {
    const collision = event.target.closest("[data-collision-key]");
    const key = collision ? collision.dataset.collisionKey : event.target.closest("[data-retry-detail]") ? selectedKey : null;
    if (!key) return;
    const record = visibleRecords.find((item) => item.key === key);
    if (record) selectRecord(record, false);
  });
  $("detail-close").addEventListener("click", () => closeDetail());
  function showCollisions(records) {
    if (detailRequest) detailRequest.abort();
    detailSequence += 1;
    selectedKey = null;
    updateActiveList();
    openDetail("겹쳐 있는 기록");
    detailEl.innerHTML = `<div class="detail-eyebrow">RECORDS AT THIS POSITION</div><h2>이 위치의 기록 ${count(records.length)}건</h2><p class="detail-place">좌표가 같거나 가까운 기록입니다. 확인할 기록을 선택하세요.</p><div class="collision-list">${records.map((record) => `<button type="button" class="collision-button" data-collision-key="${esc(record.key)}"><span class="realm-dot ${realmOf(record)}"></span><span><strong>${esc(record.p.name)}</strong><small>${record.p.kind === "site" ? "채집지" : "독립 산출 기록"} · ${esc(realmNames[realmOf(record)])}</small></span></button>`).join("")}</div>`;
  }
  function recordsAtPixel(pixel) {
    const records = new Map();
    map.forEachFeatureAtPixel(pixel, (feature) => {
      (feature.get("records") || []).forEach((record) => records.set(record.key, record));
      return undefined; // 겹친 모든 점을 모아 어느 기록도 선택 목록에서 빠지지 않게 한다.
    }, { layerFilter: (layer) => layer === pointLayer, hitTolerance: 7 });
    return Array.from(records.values());
  }
  map.on("singleclick", (event) => {
    if (picking) {
      const [rawLon, lat] = ol.proj.toLonLat(event.coordinate);
      if (!Number.isFinite(lat) || Math.abs(lat) > MAX_LAT) { notice("지도의 표시 범위 안에서 채집 위치를 선택하세요."); return; }
      const url = new URL(mapEl.dataset.siteCreate, window.location.href);
      url.searchParams.set("lat", lat.toFixed(6));
      url.searchParams.set("lon", normalizeLongitude(rawLon).toFixed(6));
      if (currentRealm !== "all") url.searchParams.set("realm", currentRealm);
      window.location.assign(url.href);
      return;
    }
    const records = recordsAtPixel(event.pixel);
    if (records.length === 1) selectRecord(records[0], false);
    else if (records.length > 1) showCollisions(records);
    else closeDetail(false);
  });
  map.on("pointermove", (event) => {
    if (event.dragging) return;
    const [lon, lat] = ol.proj.toLonLat(event.coordinate);
    $("map-coordinate").textContent = coordinateLabel(normalizeLongitude(lon), lat);
    mapEl.style.cursor = picking ? "crosshair" : recordsAtPixel(event.pixel).length ? "pointer" : "";
  });
  mapEl.addEventListener("pointerleave", () => { $("map-coordinate").textContent = "WGS 84 · 위도 / 경도"; });
  function setPicking(value) {
    picking = value;
    $("pick-banner").hidden = !value;
    $("add-site").classList.toggle("active", value);
    $("add-site").setAttribute("aria-pressed", String(value));
    mapEl.style.cursor = value ? "crosshair" : "";
    if (value) { closeDetail(false); toggleSidebar(false); mapEl.focus({ preventScroll: true }); }
  }
  $("add-site").addEventListener("click", () => setPicking(!picking));
  $("cancel-pick").addEventListener("click", () => setPicking(false));
  $("zoom-in").addEventListener("click", () => view.animate({ zoom: Math.min(18, view.getZoom() + 1), duration: motion }));
  $("zoom-out").addEventListener("click", () => view.animate({ zoom: Math.max(1, view.getZoom() - 1), duration: motion }));
  $("world-view").addEventListener("click", () => { closeDetail(false); view.animate({ center: ol.proj.fromLonLat([20, 10]), zoom: 1.7, duration: motion }); });
  $("fit-records").addEventListener("click", () => {
    if (!source.getFeatures().length) { notice(visibleRecords.length ? "현재 배경지도의 표시 범위 안에 있는 기록이 없습니다." : "표시할 채집 기록이 없습니다."); return; }
    closeDetail(false);
    toggleSidebar(false);
    view.fit(source.getExtent(), { padding: [75, 75, 70, 50], maxZoom: 12, duration: motion });
  });
  $("coordinate-toggle").addEventListener("click", () => {
    const open = $("coordinate-panel").hidden;
    $("coordinate-panel").hidden = !open;
    $("coordinate-toggle").setAttribute("aria-expanded", String(open));
    if (open) $("go-lat").focus();
  });
  $("coordinate-panel").addEventListener("submit", (event) => {
    event.preventDefault();
    const lat = Number($("go-lat").value);
    const lon = Number($("go-lon").value);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > MAX_LAT || Math.abs(lon) > 180) return;
    closeDetail(false);
    view.animate({ center: ol.proj.fromLonLat([lon, lat]), zoom: Math.max(9, view.getZoom()), duration: motion });
    $("coordinate-panel").hidden = true;
    $("coordinate-toggle").setAttribute("aria-expanded", "false");
    mapEl.focus({ preventScroll: true });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    setPicking(false);
    closeDetail(false);
    $("coordinate-panel").hidden = true;
    $("coordinate-toggle").setAttribute("aria-expanded", "false");
    toggleSidebar(false);
  });
  loadRecords();
})();
