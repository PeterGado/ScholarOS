import subprocess
import sys

# app.main builds its FastAPI() instance at import time, deciding docs_url/redoc_url/openapi_url
# from get_settings().environment in that same moment (app/main.py, 2026-10-11 production-
# readiness pass) - reimporting the already-imported module in-process wouldn't re-run that
# decision, and no precedent exists in this codebase for safely reloading app.main mid-suite
# (it also re-registers routes and conditionally initializes Sentry). A fresh subprocess per
# case is the simplest way to actually exercise the real import-time branch, mirroring this
# project's own "verify against the real running app, not just the code" discipline.
_CHECK_SCRIPT = """
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from app.main import app
print(app.docs_url, app.redoc_url, app.openapi_url)
"""


def _run_with_environment(environment: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_SCRIPT],
        env={**__import__("os").environ, "ENVIRONMENT": environment},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_docs_routes_are_disabled_in_production():
    assert _run_with_environment("production") == "None None None"


def test_docs_routes_stay_enabled_outside_production():
    assert _run_with_environment("development") == "/docs /redoc /openapi.json"
