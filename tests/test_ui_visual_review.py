from __future__ import annotations

import os
import socket
import shutil
import threading
import time
from contextlib import closing
from pathlib import Path

import httpx
import pytest
import uvicorn

playwright = pytest.importorskip("playwright.sync_api")

from app.database import get_db_session
from app.deps import get_db
from app.main import create_app


def _find_open_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


@pytest.fixture()
def ui_review_server(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_db] = override_get_db

    port = _find_open_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    timeout_at = time.time() + 10
    while time.time() < timeout_at:
        try:
            response = httpx.get(f"{base_url}/", timeout=1.5)
            if response.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("Timed out waiting for local UI review server to start.")

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_visual_review_screenshots(ui_review_server: str, seeded_notice: str) -> None:
    artifact_dir = Path("tests/.artifacts/ui-review")
    baseline_dir = Path("tests/ui-baselines")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    approve_baselines = os.environ.get("UI_REVIEW_APPROVE") == "1"

    with playwright.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except Exception as exc:  # pragma: no cover - environment-specific browser install issue
            pytest.skip(f"Playwright browser is not available: {exc}")

        page = browser.new_page(viewport={"width": 1440, "height": 1400}, color_scheme="light")
        scenarios = {
            "dashboard": "/",
            "shortlist": "/results",
            "notice-detail": f"/results/{seeded_notice}",
        }

        try:
            for name, path in scenarios.items():
                page.goto(f"{ui_review_server}{path}", wait_until="networkidle")
                screenshot_path = artifact_dir / f"{name}.png"
                baseline_path = baseline_dir / f"{name}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                assert screenshot_path.exists()
                assert screenshot_path.stat().st_size > 5_000

                if approve_baselines:
                    shutil.copyfile(screenshot_path, baseline_path)
                    continue

                if not baseline_path.exists():
                    pytest.skip(
                        "UI baseline missing. Run with UI_REVIEW_APPROVE=1 to approve screenshots first."
                    )

                assert baseline_path.read_bytes() == screenshot_path.read_bytes(), (
                    f"Visual regression detected for {name}. "
                    f"Compare {baseline_path} with {screenshot_path}."
                )
        finally:
            browser.close()