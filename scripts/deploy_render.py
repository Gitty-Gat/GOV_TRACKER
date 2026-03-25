from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import Settings


SERVICE_NAME = "civic-ledger"
HEALTH_PATH = "/healthz"


def git_remote_url() -> str:
    for remote in ("origin", "GOVTRACKER"):
        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError("No Git remote URL found for deployment.")


def github_repo_url(remote_url: str) -> str:
    clean = remote_url.strip()
    if clean.startswith("git@github.com:"):
        clean = "https://github.com/" + clean.split(":", 1)[1]
    if clean.endswith(".git"):
        clean = clean[:-4]
    return clean


def render_headers(settings: Settings) -> dict[str, str]:
    if not settings.render_api_key:
        raise RuntimeError("RENDER_API_KEY is missing.")
    return {
        "Authorization": f"Bearer {settings.render_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def list_owners(settings: Settings) -> list[dict]:
    response = requests.get(
        f"{settings.render_api_url}/owners",
        headers=render_headers(settings),
        timeout=30,
    )
    response.raise_for_status()
    owners = []
    for item in response.json():
        owner = item.get("owner", item)
        owners.append(owner)
    return owners


def choose_owner(settings: Settings) -> dict:
    owners = list_owners(settings)
    if settings.render_owner_id:
        owner = next((item for item in owners if item.get("id") == settings.render_owner_id), None)
        if not owner:
            raise RuntimeError("RENDER_OWNER_ID was provided but no matching Render workspace was found.")
        return owner
    if not owners:
        raise RuntimeError("No Render workspaces available to this API key.")
    if len(owners) == 1:
        return owners[0]
    raise RuntimeError("Multiple Render workspaces found. Set RENDER_OWNER_ID support before choosing automatically.")


def list_services(settings: Settings, owner_id: str) -> list[dict]:
    response = requests.get(
        f"{settings.render_api_url}/services",
        headers=render_headers(settings),
        params={"ownerId": owner_id, "limit": 100},
        timeout=30,
    )
    response.raise_for_status()
    services = []
    for item in response.json():
        service = item.get("service", item)
        services.append(service)
    return services


def find_existing_service(settings: Settings, owner_id: str) -> dict | None:
    for service in list_services(settings, owner_id):
        if settings.render_service_id and service.get("id") == settings.render_service_id:
            return service
        if service.get("name") == SERVICE_NAME:
            return service
    return None


def env_vars_payload(settings: Settings) -> list[dict[str, str]]:
    payload = [
        {"key": "APP_NAME", "value": settings.app_name},
        {"key": "CONGRESS_API_KEY", "value": settings.congress_api_key},
        {"key": "FEC_API_KEY", "value": settings.fec_api_key},
        {"key": "PYTHON_VERSION", "value": "3.13.0"},
        {"key": "CURRENT_CONGRESS", "value": str(settings.current_congress)},
        {"key": "DEFAULT_CYCLE", "value": str(settings.default_cycle)},
        {"key": "DATABASE_PATH", "value": settings.database_path},
        {"key": "REQUEST_TIMEOUT_SECONDS", "value": str(settings.request_timeout_seconds)},
        {"key": "OFFICIALS_SYNC_HOURS", "value": str(settings.officials_sync_hours)},
        {"key": "DETAIL_CACHE_HOURS", "value": str(settings.detail_cache_hours)},
        {"key": "ACTIVITY_CACHE_HOURS", "value": str(settings.activity_cache_hours)},
        {"key": "FINANCE_CACHE_HOURS", "value": str(settings.finance_cache_hours)},
        {"key": "PROMISE_CACHE_HOURS", "value": str(settings.promise_cache_hours)},
    ]
    if settings.database_url:
        payload.append({"key": "DATABASE_URL", "value": settings.database_url})
    return payload


def create_service(settings: Settings, owner_id: str, repo_url: str) -> dict:
    payload = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": owner_id,
        "repo": repo_url,
        "branch": "main",
        "autoDeploy": "yes",
        "envVars": env_vars_payload(settings),
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": "oregon",
            "healthCheckPath": HEALTH_PATH,
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt && (python scripts/refresh_directory_metrics.py || true)",
                "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            },
        },
    }
    response = requests.post(
        f"{settings.render_api_url}/services",
        headers=render_headers(settings),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def update_service(settings: Settings, service_id: str, repo_url: str) -> dict:
    payload = {
        "name": SERVICE_NAME,
        "repo": repo_url,
        "branch": "main",
        "autoDeploy": "yes",
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": "oregon",
            "healthCheckPath": HEALTH_PATH,
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt && (python scripts/refresh_directory_metrics.py || true)",
                "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            },
        },
    }
    response = requests.patch(
        f"{settings.render_api_url}/services/{service_id}",
        headers=render_headers(settings),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def update_env_vars(settings: Settings, service_id: str) -> None:
    response = requests.put(
        f"{settings.render_api_url}/services/{service_id}/env-vars",
        headers=render_headers(settings),
        json=env_vars_payload(settings),
        timeout=60,
    )
    response.raise_for_status()


def trigger_deploy(settings: Settings, service_id: str) -> dict:
    response = requests.post(
        f"{settings.render_api_url}/services/{service_id}/deploys",
        headers=render_headers(settings),
        json={"clearCache": "do_not_clear"},
        timeout=60,
    )
    response.raise_for_status()
    if response.content:
        return response.json()
    deploys = requests.get(
        f"{settings.render_api_url}/services/{service_id}/deploys",
        headers=render_headers(settings),
        params={"limit": 1},
        timeout=30,
    )
    deploys.raise_for_status()
    latest = deploys.json()
    return latest[0] if latest else {}


def get_service(settings: Settings, service_id: str) -> dict:
    response = requests.get(
        f"{settings.render_api_url}/services/{service_id}",
        headers=render_headers(settings),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_deploy(settings: Settings, service_id: str, deploy_id: str) -> dict:
    response = requests.get(
        f"{settings.render_api_url}/services/{service_id}/deploys/{deploy_id}",
        headers=render_headers(settings),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def wait_for_deploy(settings: Settings, service_id: str, deploy_id: str) -> dict:
    terminal = {"live", "build_failed", "update_failed", "canceled", "deactivated", "crashed"}
    while True:
        deploy = get_deploy(settings, service_id, deploy_id)
        status = deploy.get("status")
        print(f"Deploy status: {status}")
        if status in terminal:
            return deploy
        time.sleep(10)


def check_health(service_url: str) -> None:
    health = requests.get(f"{service_url.rstrip('/')}{HEALTH_PATH}", timeout=30)
    health.raise_for_status()


if __name__ == "__main__":
    settings = Settings()
    owner = choose_owner(settings)
    repo_url = github_repo_url(git_remote_url())
    existing = find_existing_service(settings, owner["id"])

    if existing:
        service_id = existing["id"]
        print(f"Using existing Render service {SERVICE_NAME} ({service_id})")
        update_service(settings, service_id, repo_url)
        update_env_vars(settings, service_id)
        deploy = trigger_deploy(settings, service_id)
        deploy_id = deploy.get("id")
    else:
        created = create_service(settings, owner["id"], repo_url)
        service_id = created["service"]["id"]
        deploy_id = created["deployId"]
        print(f"Created Render service {SERVICE_NAME} ({service_id})")

    if not deploy_id:
        raise RuntimeError("Render did not return a deploy ID.")

    final_deploy = wait_for_deploy(settings, service_id, deploy_id)
    if final_deploy.get("status") != "live":
        raise RuntimeError(f"Render deploy failed with status {final_deploy.get('status')}")

    service = get_service(settings, service_id)
    service_url = service.get("serviceDetails", {}).get("url") or service.get("url")
    if service_url:
        check_health(service_url)
        print(f"Render deployment is live: {service_url}")
    else:
        print("Render deployment is live, but no service URL was returned.")
