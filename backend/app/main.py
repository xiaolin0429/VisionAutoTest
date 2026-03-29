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
        min-height: 100vh;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at top, rgba(79, 172, 254, 0.18), transparent 38%),
          linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
      }
      .panel {
        width: min(720px, calc(100vw - 48px));
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
        <button class="primary" type="button" data-testid="cta-open-form">Open Demo Form</button>
        <button class="secondary" type="button" data-testid="cta-reset">Reset</button>
      </div>
      <section class="form-card" data-testid="demo-form" hidden>
        <label for="name-input">Operator Name</label>
        <input id="name-input" data-testid="name-input" type="text" autocomplete="off" />
        <div class="actions">
          <button class="primary" type="button" data-testid="submit-button">Submit Demo</button>
        </div>
      </section>
      <div class="result" data-testid="result-banner">Ready for execution</div>
    </main>
    <script>
      const form = document.querySelector("[data-testid='demo-form']");
      const nameInput = document.querySelector("[data-testid='name-input']");
      const resultBanner = document.querySelector("[data-testid='result-banner']");
      document.querySelector("[data-testid='cta-open-form']").addEventListener("click", () => {
        form.hidden = false;
        nameInput.focus();
        resultBanner.textContent = "Form opened";
      });
      document.querySelector("[data-testid='submit-button']").addEventListener("click", () => {
        const value = nameInput.value.trim() || "VisionAutoTest";
        resultBanner.textContent = `Hello, ${value}`;
      });
      document.querySelector("[data-testid='cta-reset']").addEventListener("click", () => {
        form.hidden = true;
        nameInput.value = "";
        resultBanner.textContent = "Ready for execution";
      });
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
