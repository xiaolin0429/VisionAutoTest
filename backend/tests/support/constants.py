from __future__ import annotations

import base64

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "test-admin-password"
TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
)
ACTUAL_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-actual"
DIFF_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-diff"
OCR_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-ocr"
BROWSER_STEPS_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Browser Steps Fixture</title>
    <style>
      body {
        margin: 0;
        font-family: Arial, sans-serif;
      }
      main {
        width: min(720px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 32px 0 96px;
      }
      #scroll-container {
        height: 180px;
        overflow: auto;
        border: 1px solid #ccd6e0;
        border-radius: 16px;
        padding: 12px;
      }
      #scroll-content {
        width: 820px;
        height: 520px;
        position: relative;
        background: linear-gradient(135deg, rgba(79, 172, 254, 0.18), rgba(20, 33, 61, 0.05));
      }
      #element-scroll-target {
        position: absolute;
        right: 24px;
        bottom: 24px;
        padding: 10px 14px;
        background: #14213d;
        color: #fff;
      }
      #page-spacer {
        height: 900px;
      }
      #long-press-target {
        margin-top: 20px;
        padding: 18px 24px;
        border: 1px dashed #8193a5;
        background: #fff;
      }
    </style>
  </head>
  <body>
    <main>
      <h1 data-testid="fixture-title">Browser Steps Fixture</h1>
      <div data-testid="navigate-status">Default View</div>
      <div data-testid="page-scroll-status">Page Not Scrolled</div>
      <div data-testid="element-scroll-status">Element Not Scrolled</div>
      <div id="scroll-container" data-testid="scroll-container">
        <div id="scroll-content">
          <div id="element-scroll-target" data-testid="element-scroll-target">Element Scroll Target</div>
        </div>
      </div>
      <button id="long-press-target" data-testid="long-press-target" type="button">Press And Hold</button>
      <div data-testid="press-status">Long Press Idle</div>
      <div id="page-spacer"></div>
    </main>
    <script>
      const params = new URLSearchParams(window.location.search);
      const view = params.get("view");
      const navigateStatus = document.querySelector("[data-testid='navigate-status']");
      const pageScrollStatus = document.querySelector("[data-testid='page-scroll-status']");
      const elementScrollStatus = document.querySelector("[data-testid='element-scroll-status']");
      const scrollContainer = document.querySelector("[data-testid='scroll-container']");
      const longPressTarget = document.querySelector("[data-testid='long-press-target']");
      const pressStatus = document.querySelector("[data-testid='press-status']");

      if (view === "details") {
        navigateStatus.textContent = "Details View";
      }

      const syncPageScrollStatus = () => {
        pageScrollStatus.textContent = window.scrollY > 80 ? "Page Scrolled" : "Page Not Scrolled";
      };
      window.addEventListener("scroll", syncPageScrollStatus, { passive: true });
      syncPageScrollStatus();

      scrollContainer.addEventListener("scroll", () => {
        const moved = scrollContainer.scrollTop > 0 || scrollContainer.scrollLeft > 0;
        elementScrollStatus.textContent = moved ? "Element Scrolled" : "Element Not Scrolled";
      });

      let longPressTimer = null;
      let longPressActive = false;
      const clearTimer = () => {
        if (longPressTimer !== null) {
          window.clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      };
      const startPress = () => {
        clearTimer();
        longPressActive = true;
        pressStatus.textContent = "Long Press Pending";
        longPressTimer = window.setTimeout(() => {
          if (longPressActive) {
            pressStatus.textContent = "Long Press Activated";
          }
        }, 650);
      };
      const stopPress = () => {
        longPressActive = false;
        clearTimer();
        if (pressStatus.textContent !== "Long Press Activated") {
          pressStatus.textContent = "Long Press Idle";
        }
      };

      longPressTarget.addEventListener("mousedown", startPress);
      longPressTarget.addEventListener("mouseup", stopPress);
      longPressTarget.addEventListener("mouseleave", stopPress);
    </script>
  </body>
</html>
"""
