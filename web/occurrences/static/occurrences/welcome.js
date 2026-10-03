/* 인사 화면은 기록 요청이 끝나면 닫는다. 배경지도 타일이나 다른 스크립트를 기다리지 않는다. */
(function () {
  "use strict";

  let startupResult = null;
  let notifySettled = null;
  document.addEventListener("slowwalker:startup-settled", function (event) {
    startupResult = Boolean(event.detail && event.detail.ok);
    if (notifySettled) notifySettled();
  });

  function initialize() {
    const screen = document.getElementById("welcome-screen");
    const status = document.getElementById("welcome-status");
    const skip = document.getElementById("welcome-skip");
    const linger = document.getElementById("welcome-linger");
    const replay = document.getElementById("welcome-replay");
    const shell = document.querySelector(".atlas-shell");
    if (!screen || !status || !skip || !linger || !shell) return;

    const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const minimumDuration = reducedMotion ? 0 : 2800;
    const fadeDuration = reducedMotion ? 0 : 280;
    const maximumDuration = 8000;
    let active = false;
    let closing = false;
    let held = false;
    let replaying = false;
    let openedAt = 0;
    let previousFocus = null;
    let minimumTimer = null;
    let deadlineTimer = null;
    let fadeTimer = null;

    function clearTimers() {
      window.clearTimeout(minimumTimer);
      window.clearTimeout(deadlineTimer);
      window.clearTimeout(fadeTimer);
      minimumTimer = deadlineTimer = fadeTimer = null;
    }

    function updateStatus() {
      if (replaying) {
        status.textContent = "지도로 돌아갈 준비가 됐어요.";
      } else if (startupResult === true) {
        status.textContent = "채집 기록을 불러왔어요. 지도로 이동할 준비가 됐어요.";
      } else if (startupResult === false) {
        status.textContent = "기록을 불러오지 못했어요. 지도에서 다시 시도할 수 있어요.";
      } else {
        status.textContent = "채집 기록을 불러오고 있어요.";
      }
    }

    function focusElement(element) {
      if (element && element.isConnected && typeof element.focus === "function") {
        element.focus({ preventScroll: true });
      }
    }

    function finish() {
      if (!active || closing) return;
      closing = true;
      clearTimers();
      screen.classList.add("is-leaving");

      function hide() {
        // 사용자가 이미 다른 곳으로 초점을 옮겼다면 다시 빼앗지 않는다.
        const hadFocus = screen.contains(document.activeElement);
        active = false;
        closing = false;
        screen.hidden = true;
        shell.inert = false;
        screen.classList.remove("is-leaving");
        screen.removeAttribute("aria-modal");
        document.removeEventListener("keydown", handleKeys, true);
        clearTimers();
        if (hadFocus) {
          const target = replaying && previousFocus && previousFocus.isConnected
            ? previousFocus : document.getElementById("map");
          focusElement(target);
        }
        previousFocus = null;
      }

      // transitionend 가 오지 않는 환경에서도 지도 잠금이 반드시 풀린다.
      if (fadeDuration) fadeTimer = window.setTimeout(hide, fadeDuration);
      else hide();
    }

    function planClose() {
      window.clearTimeout(minimumTimer);
      window.clearTimeout(deadlineTimer);
      minimumTimer = deadlineTimer = null;
      if (!active || closing || held) return;
      const elapsed = Date.now() - openedAt;

      // 스크립트 오류나 끊어진 요청에도 8초가 지나면 사용자가 지도로 갈 수 있다.
      deadlineTimer = window.setTimeout(function () {
        if (!replaying && startupResult === null) {
          status.textContent = "준비가 늦어지고 있어요. 지도를 먼저 열어요.";
        }
        finish();
      }, Math.max(0, maximumDuration - elapsed));

      if (replaying || startupResult !== null) {
        const remaining = Math.max(0, minimumDuration - elapsed);
        if (remaining) minimumTimer = window.setTimeout(finish, remaining);
        else finish();
      }
    }

    function handleKeys(event) {
      if (!active) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        finish();
        return;
      }
      if (event.key !== "Tab") return;
      const controls = Array.from(screen.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )).filter(function (element) {
        return !element.hidden && !element.closest("[hidden]") && element.getClientRects().length;
      });
      const first = controls[0] || skip;
      const last = controls[controls.length - 1] || skip;
      const focused = document.activeElement;
      if (event.shiftKey && (focused === first || !screen.contains(focused))) {
        event.preventDefault();
        focusElement(last);
      } else if (!event.shiftKey && (focused === last || !screen.contains(focused))) {
        event.preventDefault();
        focusElement(first);
      }
    }

    function show(isReplay) {
      if (active) return;
      clearTimers();
      previousFocus = document.activeElement;
      replaying = isReplay;
      held = isReplay;
      openedAt = Date.now();
      active = true;
      closing = false;
      screen.classList.remove("is-leaving");
      screen.hidden = false;
      screen.setAttribute("aria-modal", "true");
      shell.inert = true;
      skip.disabled = false;
      linger.setAttribute("aria-pressed", String(held));
      updateStatus();
      document.addEventListener("keydown", handleKeys, true);
      focusElement(skip);
      planClose();
    }

    skip.addEventListener("click", finish);
    linger.addEventListener("click", function () {
      if (!active || closing) return;
      held = !held;
      linger.setAttribute("aria-pressed", String(held));
      planClose();
    });
    if (replay) {
      replay.addEventListener("click", function () { show(true); });
      replay.hidden = false;
    }
    notifySettled = function () {
      if (!active || closing) return;
      updateStatus();
      planClose();
    };
    show(false);
  }

  // 화면 요소가 이미 있으면 뒤따르는 지도 스크립트의 다운로드보다 먼저 시간을 센다.
  if (document.getElementById("welcome-screen") && document.querySelector(".atlas-shell")) {
    initialize();
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
