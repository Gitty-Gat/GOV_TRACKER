from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Readiness = Literal["seeded", "partial", "enriched"]
PendingReadiness = Literal["pending", "seeded", "partial", "enriched"]


class OfficialCard(BaseModel):
    bioguide_id: str
    name: str
    chamber: str
    state: str
    district: int | None = None
    party: str | None = None
    image_url: str | None = None
    image_fallback_url: str | None = None
    website_url: str | None = None
    total_raised: float | None = None
    cash_on_hand: float | None = None
    top_donor_names: list[str] = Field(default_factory=list)
    efficiency_score: int | None = None
    delivery_score: int | None = None
    keeps_promises_score: int | None = None
    truth_verdict: str | None = None
    truth_badge_variant: str | None = None
    last_refreshed_at: str | None = None
    data_readiness: Readiness = "seeded"
    finance_status: PendingReadiness = "pending"
    activity_status: PendingReadiness = "pending"
    promises_status: PendingReadiness = "pending"
    priority_commitment_score: int | None = None
    pac_alignment_signal: int | None = None
    pac_share: float | None = None
    finance_available: bool = False


class DirectoryMetric(BaseModel):
    finance_available: bool = False
    candidate_id: str | None = None
    principal_committee_id: str | None = None
    total_raised: float | None = None
    cash_on_hand: float | None = None
    pac_share: float | None = None
    top_donor_names: list[str] = Field(default_factory=list)
    efficiency_score: int | None = None
    delivery_score: int | None = None
    keeps_promises_score: int | None = None
    truth_verdict: str | None = None
    truth_badge_variant: str | None = None
    last_refreshed_at: str | None = None
    data_readiness: Readiness = "seeded"
    finance_status: PendingReadiness = "pending"
    activity_status: PendingReadiness = "pending"
    promises_status: PendingReadiness = "pending"
    priority_commitment_score: int | None = None
    pac_alignment_signal: int | None = None
    years_in_office: int | None = None


class PromiseItem(BaseModel):
    title: str
    description: str
    topic: str
    source_label: str
    source_url: str | None = None
    confidence: float = 0.0
    evidence_strength: float | None = None
    evidence_label: str | None = None
    provenance: Literal["manual", "inferred"] = "inferred"
    evidence: str | None = None


class BillRecord(BaseModel):
    title: str
    bill_number: str
    congress: int
    introduced_date: str | None = None
    policy_area: str = "Unspecified"
    latest_action_text: str = ""
    latest_action_date: str | None = None
    url: str | None = None
    sponsorship: Literal["sponsored", "cosponsored"] = "sponsored"
    stage: str = "introduced"
    stage_weight: float = 0.0
    impact_summary: str = ""


class PolicyAreaStat(BaseModel):
    name: str
    weight: float
    bill_count: int


class ActivitySummary(BaseModel):
    status: PendingReadiness = "seeded"
    sponsored_count_total: int = 0
    cosponsored_count_total: int = 0
    enacted_count: int = 0
    passed_count: int = 0
    committee_progress_count: int = 0
    sampled_sponsored_count: int = 0
    sampled_cosponsored_count: int = 0
    top_policy_areas: list[PolicyAreaStat] = Field(default_factory=list)
    recent_bills: list[BillRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DonorRecipient(BaseModel):
    name: str
    amount: float
    recipient: str | None = None
    candidate_name: str | None = None
    committee_id: str | None = None


class DonorRecord(BaseModel):
    name: str
    amount: float
    donor_type: str
    city: str | None = None
    state: str | None = None
    employer: str | None = None
    occupation: str | None = None
    contributor_id: str | None = None
    source_url: str | None = None
    other_recipients: list[DonorRecipient] = Field(default_factory=list)


class StateContribution(BaseModel):
    state: str
    amount: float


class PacAuditTrail(BaseModel):
    pac_name: str
    pac_committee_id: str | None = None
    amount_to_official: float = 0.0
    inbound_sources: list[DonorRecord] = Field(default_factory=list)
    outbound_targets: list[DonorRecipient] = Field(default_factory=list)


class FinanceSummary(BaseModel):
    status: PendingReadiness = "pending"
    available: bool = False
    warning: str | None = None
    candidate_id: str | None = None
    principal_committee_id: str | None = None
    principal_committee_name: str | None = None
    cycle: int | None = None
    total_raised: float | None = None
    cash_on_hand: float | None = None
    disbursements: float | None = None
    individual_contributions: float | None = None
    pac_contributions: float | None = None
    organized_committee_contributions: float | None = None
    transfer_contributions: float | None = None
    other_receipts: float | None = None
    constituent_share: float | None = None
    in_state_share_basis_amount: float | None = None
    in_state_share_label: str | None = None
    pac_share: float | None = None
    itemized_share: float | None = None
    coverage_end_date: str | None = None
    donor_state_totals: list[StateContribution] = Field(default_factory=list)
    top_donors: list[DonorRecord] = Field(default_factory=list)
    top_pac_donors: list[DonorRecord] = Field(default_factory=list)
    pac_audit_trails: list[PacAuditTrail] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PromiseTopicScore(BaseModel):
    topic: str
    promise_title: str
    score: int
    matched_actions: list[BillRecord] = Field(default_factory=list)
    matched_action_count: int = 0
    delivery_label: str = "No visible movement"
    delivery_stage_summary: str = ""
    rationale: str


class DeliveryScore(BaseModel):
    overall_score: int | None = None
    label: str = "Insufficient data"
    explanation: str = ""
    topic_scores: list[PromiseTopicScore] = Field(default_factory=list)


class OfficialDetail(BaseModel):
    member: dict[str, Any]
    card: OfficialCard
    activity: ActivitySummary
    finance: FinanceSummary
    promises: list[PromiseItem]
    delivery_score: DeliveryScore
    data_readiness: Readiness = "seeded"
    methodology_notes: list[str] = Field(default_factory=list)
