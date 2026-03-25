from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.db import Database
from app.models import PromiseItem
from app.settings import get_settings


TOPIC_RULES: list[dict[str, Any]] = [
    {"topic": "Jobs & Economy", "keywords": ["jobs", "economy", "small business", "manufacturing", "workers", "wages", "trade"]},
    {"topic": "Infrastructure", "keywords": ["infrastructure", "bridge", "roads", "transportation", "broadband", "transit", "port"]},
    {"topic": "Public Safety & Guns", "keywords": ["gun", "crime", "public safety", "firearm", "law enforcement"]},
    {"topic": "Healthcare", "keywords": ["health", "healthcare", "medicare", "medicaid", "mental health", "drug costs"]},
    {"topic": "Immigration", "keywords": ["immigration", "border", "asylum", "visa", "citizenship"]},
    {"topic": "Energy & Climate", "keywords": ["energy", "climate", "clean energy", "oil", "gas", "emissions"]},
    {"topic": "Education", "keywords": ["education", "schools", "students", "teachers", "college"]},
    {"topic": "Veterans", "keywords": ["veterans", "va", "military families"]},
    {"topic": "Agriculture", "keywords": ["farm", "agriculture", "rural", "crops", "livestock"]},
    {"topic": "Taxes & Budget", "keywords": ["tax", "budget", "spending", "deficit", "fiscal"]},
]


class PromiseService:
    def __init__(self, db: Database | None = None) -> None:
        self.settings = get_settings()
        self.db = db or Database()
        self.manual_path = Path("data/manual_promises.json")

    def get_promises(self, member: dict[str, Any], force: bool = False) -> list[PromiseItem]:
        bioguide_id = member["bioguideId"]
        cached = self.db.load_snapshot("promises", bioguide_id)
        if cached and not force:
            payload, fetched_at = cached
            if datetime.now(timezone.utc) - fetched_at < timedelta(hours=self.settings.promise_cache_hours):
                return [PromiseItem.model_validate(item) for item in payload.get("items", [])]

        manual = self._load_manual_promises().get(bioguide_id, [])
        if manual:
            items = [PromiseItem.model_validate({**item, "provenance": "manual"}) for item in manual]
            self.db.save_snapshot("promises", bioguide_id, {"items": [item.model_dump(mode="json") for item in items]})
            return items

        inferred = self._infer_from_official_site(member.get("officialWebsiteUrl"))
        self.db.save_snapshot("promises", bioguide_id, {"items": [item.model_dump(mode="json") for item in inferred]})
        return inferred

    def _load_manual_promises(self) -> dict[str, list[dict[str, Any]]]:
        if not self.manual_path.exists():
            return {}
        return json.loads(self.manual_path.read_text(encoding="utf-8"))

    def _infer_from_official_site(self, official_website: str | None) -> list[PromiseItem]:
        if not official_website:
            return []
        try:
            response = requests.get(
                official_website,
                timeout=self.settings.request_timeout_seconds,
                headers={"User-Agent": "CivicLedger/0.1"},
            )
            response.raise_for_status()
        except requests.RequestException:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        text_fragments: list[tuple[str, int]] = []
        for tag_name, weight in (("h1", 5), ("h2", 4), ("h3", 3), ("a", 2), ("p", 1), ("li", 1)):
            for tag in soup.find_all(tag_name):
                text = " ".join(tag.get_text(" ", strip=True).split())
                if 3 <= len(text) <= 180:
                    text_fragments.append((text, weight))

        topic_hits: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for text, weight in text_fragments:
            normalized = text.lower()
            for rule in TOPIC_RULES:
                if any(keyword in normalized for keyword in rule["keywords"]):
                    topic_hits[rule["topic"]].append((text, weight))

        ranked_topics = sorted(topic_hits.items(), key=lambda item: sum(weight for _, weight in item[1]), reverse=True)[:4]
        items: list[PromiseItem] = []
        for topic, evidence_items in ranked_topics:
            evidence_text = evidence_items[0][0]
            confidence = min(0.92, round(sum(weight for _, weight in evidence_items) / 12, 2))
            items.append(
                PromiseItem(
                    title=topic,
                    description=f"Inferred priority from official website language around {topic.lower()}.",
                    topic=topic,
                    source_label="Official website issue language",
                    source_url=official_website,
                    confidence=confidence,
                    provenance="inferred",
                    evidence=_clean_evidence(evidence_text),
                )
            )
        return items


def _clean_evidence(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:180]
