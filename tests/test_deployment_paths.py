from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_healthcheck_script(tmp_path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)
    if extra_env:
        env.update(extra_env)
    script = (
        "from fastapi.testclient import TestClient; "
        "from app.main import app; "
        "response = TestClient(app).get('/healthz'); "
        "print(response.status_code); "
        "print(response.json()['status'])"
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_app_starts_from_non_repo_cwd(tmp_path):
    result = _run_healthcheck_script(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "200" in result.stdout
    assert "ok" in result.stdout


def test_healthcheck_does_not_require_live_database_at_import_time(tmp_path):
    result = _run_healthcheck_script(
        tmp_path,
        {
            "DATABASE_URL": "postgresql://user:pass@203.0.113.1:5432/civic_ledger?connect_timeout=1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "200" in result.stdout
    assert "ok" in result.stdout
