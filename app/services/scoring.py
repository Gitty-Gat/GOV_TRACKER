from __future__ import annotations

from app.models import ActivitySummary, DeliveryScore, PromiseItem, PromiseTopicScore


PROMISE_POLICY_MAP: dict[str, list[str]] = {
    "Jobs & Economy": ["Economics and Public Finance", "Labor and Employment", "Commerce", "Taxation"],
    "Infrastructure": ["Transportation and Public Works", "Public Lands and Natural Resources", "Housing and Community Development"],
    "Public Safety & Guns": ["Crime and Law Enforcement", "Armed Forces and National Security", "Civil Rights and Liberties, Minority Issues"],
    "Healthcare": ["Health", "Families", "Social Welfare"],
    "Immigration": ["Immigration", "Foreign Trade and International Finance"],
    "Energy & Climate": ["Energy", "Environmental Protection", "Public Lands and Natural Resources"],
    "Education": ["Education"],
    "Veterans": ["Armed Forces and National Security", "Health"],
    "Agriculture": ["Agriculture and Food"],
    "Taxes & Budget": ["Taxation", "Economics and Public Finance", "Government Operations and Politics"],
}


def compute_delivery_score(promises: list[PromiseItem], activity: ActivitySummary) -> DeliveryScore:
    if not promises or not activity.recent_bills:
        return DeliveryScore(
            overall_score=0,
            label="Insufficient data",
            explanation="The score becomes meaningful after the dashboard has both issue priorities and recent legislative activity.",
        )

    topic_scores: list[PromiseTopicScore] = []
    total = 0
    for promise in promises:
        mapped_areas = PROMISE_POLICY_MAP.get(promise.topic, [promise.topic])
        relevant_bills = [bill for bill in activity.recent_bills if bill.policy_area in mapped_areas]
        relevant_bills.sort(key=lambda bill: bill.stage_weight, reverse=True)
        raw_score = sum(bill.stage_weight for bill in relevant_bills[:6]) * max(0.55, promise.confidence)
        score = min(100, round(raw_score * 7))
        total += score
        topic_scores.append(
            PromiseTopicScore(
                topic=promise.topic,
                promise_title=promise.title,
                score=score,
                matched_actions=relevant_bills[:4],
                rationale=_build_rationale(relevant_bills, mapped_areas),
            )
        )

    overall = round(total / len(promises))
    return DeliveryScore(
        overall_score=overall,
        label=_label_for_score(overall),
        explanation=(
            "This index compares stated priorities with recent sponsored and cosponsored legislation, "
            "giving more weight to sponsored bills and bills that advanced beyond committee."
        ),
        topic_scores=topic_scores,
    )


def summarize_finance_alignment(constituent_share: float | None, pac_share: float | None) -> str:
    if constituent_share is None or pac_share is None:
        return "Funding mix becomes more useful after a full finance refresh with state and committee aggregates."
    if constituent_share >= 0.4 and pac_share <= 0.2:
        return "Fundraising is tilted toward individual donors, with a comparatively lighter PAC share."
    if pac_share >= 0.3:
        return "A sizable portion of this campaign committee's funding comes from PACs and other organized committees."
    return "The funding mix is blended between individual donors and organized committees."


def _build_rationale(relevant_bills, mapped_areas: list[str]) -> str:
    if not relevant_bills:
        return f"No sampled bills in the recent activity window matched {', '.join(mapped_areas)}."
    best = relevant_bills[0]
    return f"Recent activity in {', '.join(mapped_areas)} exists, led by {best.bill_number} which is currently at the {best.stage} stage."


def _label_for_score(score: int) -> str:
    if score >= 75:
        return "Strong follow-through"
    if score >= 50:
        return "Mixed but active"
    if score >= 25:
        return "Early or uneven"
    return "Low visible follow-through"
