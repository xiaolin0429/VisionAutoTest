from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.http import ApiError, RequestIDMiddleware, error_response, success_response
from app.db.session import init_db

settings = get_settings()

DEMO_ACCEPTANCE_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>VisionAutoTest Demo Target</title>
    <style>
      :root {
        color-scheme: light;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        background: #f4f7fb;
        color: #14213d;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        padding: 48px 0 96px;
        background:
          radial-gradient(circle at top, rgba(79, 172, 254, 0.18), transparent 38%),
          linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
      }
      .panel {
        width: min(720px, calc(100vw - 48px));
        margin: 0 auto;
        padding: 40px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid rgba(20, 33, 61, 0.08);
        box-shadow: 0 24px 60px rgba(20, 33, 61, 0.16);
      }
      .eyebrow {
        display: inline-flex;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(15, 76, 129, 0.08);
        color: #0f4c81;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      h1 {
        margin: 18px 0 10px;
        font-size: 42px;
        line-height: 1.1;
      }
      p {
        margin: 0;
        font-size: 18px;
        line-height: 1.6;
        color: #405164;
      }
      .actions {
        margin-top: 28px;
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
      button {
        border: 0;
        border-radius: 14px;
        padding: 14px 20px;
        font-size: 16px;
        font-weight: 700;
        cursor: pointer;
      }
      .primary {
        background: #14213d;
        color: #ffffff;
      }
      .secondary {
        background: #dbe9f8;
        color: #0f4c81;
      }
      .form-card {
        margin-top: 26px;
        padding: 24px;
        border-radius: 20px;
        background: #f8fbff;
        border: 1px solid rgba(15, 76, 129, 0.12);
      }
      .section-title {
        margin: 0 0 12px;
        font-size: 18px;
        font-weight: 800;
      }
      .helper {
        margin-top: 10px;
        font-size: 14px;
        color: #526274;
      }
      .badge {
        display: inline-flex;
        margin-top: 16px;
        padding: 8px 12px;
        border-radius: 999px;
        background: #dbe9f8;
        color: #0f4c81;
        font-size: 13px;
        font-weight: 700;
      }
      .scroll-shell {
        margin-top: 18px;
        display: grid;
        gap: 16px;
      }
      .scroll-status {
        font-size: 14px;
        font-weight: 700;
        color: #0f4c81;
      }
      .scroll-box {
        height: 180px;
        overflow: auto;
        padding: 16px;
        border-radius: 18px;
        background: #ffffff;
        border: 1px solid rgba(20, 33, 61, 0.12);
      }
      .scroll-content {
        width: 920px;
        height: 520px;
        padding: 20px;
        border-radius: 16px;
        background:
          linear-gradient(135deg, rgba(79, 172, 254, 0.16), rgba(20, 33, 61, 0.04)),
          #f8fbff;
        position: relative;
      }
      .scroll-target {
        position: absolute;
        right: 28px;
        bottom: 28px;
        padding: 10px 14px;
        border-radius: 12px;
        background: #14213d;
        color: #ffffff;
        font-weight: 700;
      }
      .page-spacer {
        margin-top: 28px;
        height: 900px;
        border-radius: 24px;
        background:
          linear-gradient(180deg, rgba(20, 33, 61, 0.02), rgba(79, 172, 254, 0.18));
        position: relative;
      }
      .page-target {
        position: absolute;
        left: 28px;
        bottom: 28px;
        padding: 12px 16px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid rgba(20, 33, 61, 0.12);
        font-weight: 700;
      }
      .press-target {
        user-select: none;
        border-radius: 20px;
        padding: 28px;
        border: 1px dashed rgba(20, 33, 61, 0.24);
        background: #ffffff;
        font-size: 18px;
        font-weight: 700;
        color: #14213d;
        text-align: center;
      }
      label {
        display: block;
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 8px;
      }
      input {
        width: 100%;
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid rgba(20, 33, 61, 0.16);
        font-size: 16px;
      }
      .result {
        margin-top: 20px;
        padding: 16px 18px;
        min-height: 60px;
        border-radius: 16px;
        background: #14213d;
        color: #ffffff;
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 0.02em;
        display: flex;
        align-items: center;
      }
      [hidden] {
        display: none !important;
      }
    </style>
  </head>
  <body>
    <main class="panel">
      <span class="eyebrow" data-testid="demo-badge">Seeded Acceptance Target</span>
      <h1 data-testid="hero-title">VisionAutoTest Demo Target</h1>
      <p data-testid="hero-copy">
        This page is shipped with the backend so the first acceptance run does not depend on any external app.
      </p>
      <div class="actions">
        <a class="secondary" href="/demo/acceptance-target?view=details" data-testid="nav-details-link">Details View</a>
        <a class="secondary" href="/demo/acceptance-target?view=lab" data-testid="nav-lab-link">Interaction Lab</a>
      </div>
      <div class="badge" data-testid="navigate-status">Default View</div>
      <div class="actions">
        <button class="primary" type="button" data-testid="cta-open-form">Open Demo Form</button>
        <button class="secondary" type="button" data-testid="cta-reset">Reset</button>
      </div>
      <section class="form-card" data-testid="demo-form">
        <label for="name-input">Operator Name</label>
        <input id="name-input" data-testid="name-input" type="text" autocomplete="off" />
        <div class="actions">
          <button class="primary" type="button" data-testid="submit-button">Submit Demo</button>
        </div>
      </section>
      <div class="result" data-testid="result-banner">Ready for execution</div>
      <section class="form-card" data-testid="scroll-lab">
        <h2 class="section-title">Scroll Lab</h2>
        <div class="scroll-shell">
          <div class="scroll-status" data-testid="page-scroll-status">Page Not Scrolled</div>
          <div class="scroll-status" data-testid="element-scroll-status">Element Not Scrolled</div>
          <div class="scroll-box" data-testid="scroll-container">
            <div class="scroll-content">
              <div>Scroll inside this container to reach the target chip.</div>
              <div class="scroll-target" data-testid="element-scroll-target">Element Scroll Target</div>
            </div>
          </div>
        </div>
        <p class="helper">This area is used to validate element-level scrolling and page-level scrolling.</p>
      </section>
      <section class="form-card" data-testid="long-press-lab">
        <h2 class="section-title">Long Press Lab</h2>
        <button class="press-target" type="button" data-testid="long-press-target">Press And Hold</button>
        <div class="badge" data-testid="press-status">Long Press Idle</div>
      </section>
      <div class="page-spacer" data-testid="page-scroll-area">
        <div class="page-target" data-testid="page-scroll-target">Page Scroll Target</div>
      </div>
    </main>
    <script>
      const heroTitle = document.querySelector("[data-testid='hero-title']");
      const heroCopy = document.querySelector("[data-testid='hero-copy']");
      const form = document.querySelector("[data-testid='demo-form']");
      const nameInput = document.querySelector("[data-testid='name-input']");
      const resultBanner = document.querySelector("[data-testid='result-banner']");
      const navigateStatus = document.querySelector("[data-testid='navigate-status']");
      const pageScrollStatus = document.querySelector("[data-testid='page-scroll-status']");
      const elementScrollStatus = document.querySelector("[data-testid='element-scroll-status']");
      const scrollContainer = document.querySelector("[data-testid='scroll-container']");
      const pressStatus = document.querySelector("[data-testid='press-status']");
      const longPressTarget = document.querySelector("[data-testid='long-press-target']");
      const params = new URLSearchParams(window.location.search);
      const view = params.get("view");

      if (view === "details") {
        heroTitle.textContent = "VisionAutoTest Details View";
        heroCopy.textContent = "This query view is used to validate navigate steps during execution.";
        navigateStatus.textContent = "Details View";
        resultBanner.textContent = "Details view loaded";
      } else if (view === "lab") {
        navigateStatus.textContent = "Interaction Lab";
      }

      document.querySelector("[data-testid='cta-open-form']").addEventListener("click", () => {
        form.hidden = false;
        form.scrollIntoView({ block: "center", behavior: "instant" });
        nameInput.focus();
        resultBanner.textContent = "Form opened";
      });
      document.querySelector("[data-testid='submit-button']").addEventListener("click", () => {
        const value = nameInput.value.trim() || "VisionAutoTest";
        resultBanner.textContent = `Hello, ${value}`;
      });
      document.querySelector("[data-testid='cta-reset']").addEventListener("click", () => {
        form.hidden = false;
        nameInput.value = "";
        nameInput.focus();
        resultBanner.textContent = "Ready for execution";
      });

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
      let longPressArmed = false;
      const clearLongPressTimer = () => {
        if (longPressTimer !== null) {
          window.clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      };
      const startLongPress = () => {
        clearLongPressTimer();
        longPressArmed = true;
        pressStatus.textContent = "Long Press Pending";
        longPressTimer = window.setTimeout(() => {
          if (longPressArmed) {
            pressStatus.textContent = "Long Press Activated";
          }
        }, 650);
      };
      const stopLongPress = () => {
        longPressArmed = false;
        clearLongPressTimer();
        if (pressStatus.textContent !== "Long Press Activated") {
          pressStatus.textContent = "Long Press Idle";
        }
      };

      longPressTarget.addEventListener("mousedown", startLongPress);
      longPressTarget.addEventListener("mouseup", stopLongPress);
      longPressTarget.addEventListener("mouseleave", stopLongPress);
      longPressTarget.addEventListener("touchstart", startLongPress, { passive: true });
      longPressTarget.addEventListener("touchend", stopLongPress);
      longPressTarget.addEventListener("touchcancel", stopLongPress);
    </script>
  </body>
</html>
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(request, exc)


@app.get("/healthz")
def healthz(request: Request):
    return success_response(request, {"status": "ok", "service": settings.app_name})


@app.get("/demo/acceptance-target", response_class=HTMLResponse, include_in_schema=False)
def demo_acceptance_target():
    return HTMLResponse(DEMO_ACCEPTANCE_HTML)


app.include_router(api_router, prefix=settings.api_v1_prefix)
