from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_app_starts_from_non_repo_cwd(tmp_path):
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)
    script = (
        "from fastapi.testclient import TestClient; "
        "from app.main import app; "
        "response = TestClient(app).get('/healthz'); "
        "print(response.status_code); "
        "print(response.json()['status'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "200" in result.stdout
    assert "ok" in result.stdout
