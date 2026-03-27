from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - psycopg is optional for local SQLite fallback
    psycopg = None
    dict_row = None

from app.models import OfficialCard
from app.settings import get_settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, database_path: str | None = None) -> None:
        settings = get_settings()
        self.database_url = settings.database_url
        self.backend = "postgres" if self.database_url and not self.database_url.startswith("sqlite") else "sqlite"
        self.database_path = Path(database_path or settings.database_path)
        self._persistent_connection: Any | None = None
        if self.backend == "sqlite":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        elif psycopg is None:
            raise RuntimeError("DATABASE_URL was provided, but psycopg is not installed.")
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self._persistent_connection is not None:
            connection = self._persistent_connection
            try:
                yield connection
                connection.commit()
            finally:
                return
        connection = self._open_connection()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @contextmanager
    def persistent_connection(self) -> Iterator[None]:
        if self._persistent_connection is not None:
            yield
            return
        connection = self._open_connection()
        self._persistent_connection = connection
        try:
            yield
        finally:
            connection.commit()
            connection.close()
            self._persistent_connection = None

    def _open_connection(self) -> Any:
        if self.backend == "postgres":
            return psycopg.connect(self.database_url, row_factory=dict_row)
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _ensure_schema(self) -> None:
        with self.connect() as connection:
            statements = [
                """
                CREATE TABLE IF NOT EXISTS officials (
                    bioguide_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    chamber TEXT NOT NULL,
                    state TEXT NOT NULL,
                    district INTEGER,
                    party TEXT,
                    image_url TEXT,
                    image_fallback_url TEXT,
                    website_url TEXT,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_key TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_officials_lookup ON officials (chamber, state, party, name)",
                "CREATE INDEX IF NOT EXISTS idx_snapshots_namespace ON snapshots (namespace, fetched_at)",
                "CREATE INDEX IF NOT EXISTS idx_snapshots_namespace_key ON snapshots (namespace, snapshot_key)",
            ]
            for statement in statements:
                self._execute(connection, statement)

            if self.backend == "postgres":
                self._execute(connection, "ALTER TABLE officials ADD COLUMN IF NOT EXISTS image_fallback_url TEXT")
            else:
                columns = {row["name"] for row in self._execute(connection, "PRAGMA table_info(officials)").fetchall()}
                if "image_fallback_url" not in columns:
                    self._execute(connection, "ALTER TABLE officials ADD COLUMN image_fallback_url TEXT")

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as connection:
            self._execute(
                connection,
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
            row = self._execute(
                connection,
                "SELECT meta_value FROM app_meta WHERE meta_key = ?",
                (key,),
            ).fetchone()
        return row["meta_value"] if row else None

    def upsert_official(self, official: dict[str, Any]) -> None:
        chamber = _current_chamber(official)
        with self.connect() as connection:
            self._execute(
                connection,
                """
                INSERT INTO officials (
                    bioguide_id,
                    name,
                    chamber,
                    state,
                    district,
                    party,
                    image_url,
                    image_fallback_url,
                    website_url,
                    payload,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bioguide_id)
                DO UPDATE SET
                    name = excluded.name,
                    chamber = excluded.chamber,
                    state = excluded.state,
                    district = excluded.district,
                    party = excluded.party,
                    image_url = excluded.image_url,
                    image_fallback_url = excluded.image_fallback_url,
                    website_url = COALESCE(excluded.website_url, officials.website_url),
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
                    official.get("image_fallback_url"),
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
        like_operator = "ILIKE" if self.backend == "postgres" else "LIKE"
        if search:
            clauses.append(f"(name {like_operator} ? OR state {like_operator} ?)")
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
            "SELECT bioguide_id, name, chamber, state, district, party, image_url, image_fallback_url, website_url "
            f"FROM officials {where} ORDER BY chamber, state, name"
        )
        with self.connect() as connection:
            rows = self._execute(connection, query, tuple(values)).fetchall()
        return [
            OfficialCard(
                bioguide_id=row["bioguide_id"],
                name=row["name"],
                chamber=row["chamber"],
                state=row["state"],
                district=row["district"],
                party=row["party"],
                image_url=row["image_url"],
                image_fallback_url=row["image_fallback_url"],
                website_url=row["website_url"],
            )
            for row in rows
        ]

    def official_count(self) -> int:
        with self.connect() as connection:
            row = self._execute(connection, "SELECT COUNT(*) AS total FROM officials").fetchone()
        return int(row["total"]) if row else 0

    def get_official_payload(self, bioguide_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = self._execute(
                connection,
                "SELECT payload FROM officials WHERE bioguide_id = ?",
                (bioguide_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_official_payloads(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = self._execute(connection, "SELECT payload FROM officials").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get_official_card(self, bioguide_id: str) -> OfficialCard | None:
        with self.connect() as connection:
            row = self._execute(
                connection,
                """
                SELECT bioguide_id, name, chamber, state, district, party, image_url, image_fallback_url, website_url
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
            image_fallback_url=row["image_fallback_url"],
            website_url=row["website_url"],
        )

    def save_snapshot(self, namespace: str, key: str, payload: dict[str, Any]) -> None:
        snapshot_key = f"{namespace}:{key}"
        with self.connect() as connection:
            self._execute(
                connection,
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
            row = self._execute(
                connection,
                "SELECT payload, fetched_at FROM snapshots WHERE snapshot_key = ?",
                (snapshot_key,),
            ).fetchone()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        return json.loads(row["payload"]), fetched_at

    def list_namespace_snapshots(self, namespace: str) -> dict[str, tuple[dict[str, Any], datetime]]:
        with self.connect() as connection:
            rows = self._execute(
                connection,
                "SELECT snapshot_key, payload, fetched_at FROM snapshots WHERE namespace = ?",
                (namespace,),
            ).fetchall()
        snapshots: dict[str, tuple[dict[str, Any], datetime]] = {}
        prefix = f"{namespace}:"
        for row in rows:
            snapshot_key = row["snapshot_key"]
            key = snapshot_key[len(prefix) :] if snapshot_key.startswith(prefix) else snapshot_key
            snapshots[key] = (json.loads(row["payload"]), datetime.fromisoformat(row["fetched_at"]))
        return snapshots

    def _execute(self, connection: Any, query: str, params: tuple[Any, ...] = ()) -> Any:
        sql = query.replace("?", "%s") if self.backend == "postgres" else query
        return connection.execute(sql, params)


def _current_chamber(official: dict[str, Any]) -> str:
    terms = official.get("terms") or []
    if terms:
        last_term = terms[-1]
        return last_term.get("chamber", official.get("chamber", "Unknown"))
    return official.get("chamber", "Unknown")
