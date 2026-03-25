from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.models import OfficialCard
from app.settings import get_settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, database_path: str | None = None) -> None:
        settings = get_settings()
        self.database_path = Path(database_path or settings.database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS officials (
                    bioguide_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    chamber TEXT NOT NULL,
                    state TEXT NOT NULL,
                    district INTEGER,
                    party TEXT,
                    image_url TEXT,
                    website_url TEXT,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_key TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_meta (meta_key, meta_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(meta_key)
                DO UPDATE SET
                    meta_value = excluded.meta_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, utc_now_iso()),
            )

    def get_meta(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT meta_value FROM app_meta WHERE meta_key = ?",
                (key,),
            ).fetchone()
        return row["meta_value"] if row else None

    def upsert_official(self, official: dict[str, Any]) -> None:
        chamber = _current_chamber(official)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO officials (
                    bioguide_id,
                    name,
                    chamber,
                    state,
                    district,
                    party,
                    image_url,
                    website_url,
                    payload,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bioguide_id)
                DO UPDATE SET
                    name = excluded.name,
                    chamber = excluded.chamber,
                    state = excluded.state,
                    district = excluded.district,
                    party = excluded.party,
                    image_url = excluded.image_url,
                    website_url = excluded.website_url,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    official["bioguide_id"],
                    official["name"],
                    chamber,
                    official["state"],
                    official.get("district"),
                    official.get("party"),
                    official.get("image_url"),
                    official.get("website_url"),
                    json.dumps(official),
                    utc_now_iso(),
                ),
            )

    def list_officials(
        self,
        search: str | None = None,
        chamber: str | None = None,
        party: str | None = None,
        state: str | None = None,
    ) -> list[OfficialCard]:
        clauses: list[str] = []
        values: list[Any] = []
        if search:
            clauses.append("(name LIKE ? OR state LIKE ?)")
            term = f"%{search}%"
            values.extend([term, term])
        if chamber:
            clauses.append("chamber = ?")
            values.append(chamber)
        if party:
            clauses.append("party = ?")
            values.append(party)
        if state:
            clauses.append("state = ?")
            values.append(state)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = (
            "SELECT bioguide_id, name, chamber, state, district, party, image_url, website_url "
            f"FROM officials {where} ORDER BY chamber, state, name"
        )
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [
            OfficialCard(
                bioguide_id=row["bioguide_id"],
                name=row["name"],
                chamber=row["chamber"],
                state=row["state"],
                district=row["district"],
                party=row["party"],
                image_url=row["image_url"],
                website_url=row["website_url"],
            )
            for row in rows
        ]

    def official_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM officials").fetchone()
        return int(row["total"]) if row else 0

    def get_official_payload(self, bioguide_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM officials WHERE bioguide_id = ?",
                (bioguide_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def get_official_card(self, bioguide_id: str) -> OfficialCard | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT bioguide_id, name, chamber, state, district, party, image_url, website_url
                FROM officials
                WHERE bioguide_id = ?
                """,
                (bioguide_id,),
            ).fetchone()
        if not row:
            return None
        return OfficialCard(
            bioguide_id=row["bioguide_id"],
            name=row["name"],
            chamber=row["chamber"],
            state=row["state"],
            district=row["district"],
            party=row["party"],
            image_url=row["image_url"],
            website_url=row["website_url"],
        )

    def save_snapshot(self, namespace: str, key: str, payload: dict[str, Any]) -> None:
        snapshot_key = f"{namespace}:{key}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshots (snapshot_key, namespace, payload, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_key)
                DO UPDATE SET
                    payload = excluded.payload,
                    fetched_at = excluded.fetched_at
                """,
                (snapshot_key, namespace, json.dumps(payload), utc_now_iso()),
            )

    def load_snapshot(self, namespace: str, key: str) -> tuple[dict[str, Any], datetime] | None:
        snapshot_key = f"{namespace}:{key}"
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload, fetched_at FROM snapshots WHERE snapshot_key = ?",
                (snapshot_key,),
            ).fetchone()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        return json.loads(row["payload"]), fetched_at


def _current_chamber(official: dict[str, Any]) -> str:
    terms = official.get("terms") or []
    if terms:
        last_term = terms[-1]
        return last_term.get("chamber", official.get("chamber", "Unknown"))
    return official.get("chamber", "Unknown")
