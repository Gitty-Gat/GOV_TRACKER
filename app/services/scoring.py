from __future__ import annotations

from app.models import ActivitySummary, BillRecord, DeliveryScore, PromiseItem, PromiseTopicScore


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
            "This index averages weighted follow-through across stated priorities, with more credit for sponsored bills and bills that advanced."
        ),
        topic_scores=topic_scores,
    )


def compute_keeps_promises_score(promises: list[PromiseItem], activity: ActivitySummary) -> int:
    if not promises:
        return 0
    if not activity.recent_bills:
        return 0
    matched = 0
    for promise in promises:
        mapped_areas = PROMISE_POLICY_MAP.get(promise.topic, [promise.topic])
        if any(bill.policy_area in mapped_areas for bill in activity.recent_bills):
            matched += 1
    return round((matched / len(promises)) * 100)


def summarize_bill_impact(bill: BillRecord) -> str:
    title = (bill.title or "").lower()
    policy_area = (bill.policy_area or "").lower()
    stage = bill.stage

    candidates = [
        ("tax", "Changes taxes for local families and employers."),
        ("health", "Affects health coverage or care access locally."),
        ("veteran", "Targets benefits or services for veterans."),
        ("school", "Changes schools or education access locally."),
        ("education", "Changes schools or education access locally."),
        ("bridge", "Supports transportation and public works funding."),
        ("road", "Supports transportation and public works funding."),
        ("infrastructure", "Supports transportation and public works funding."),
        ("energy", "Changes energy costs or supply reliability."),
        ("housing", "Touches housing costs or local development."),
        ("crime", "Affects policing or public safety policy."),
        ("immigration", "Changes border or immigration enforcement policy."),
        ("small business", "Could affect small-business costs or growth."),
        ("agriculture", "Affects farming, food, or rural producers."),
    ]
    haystack = f"{title} {policy_area}"
    for needle, summary in candidates:
        if needle in haystack:
            return _limit_words(summary, 10)

    stage_summary = {
        "enacted": "Has become law with direct local impact.",
        "passed": "Advanced past one chamber and could aid constituents.",
        "committee": "Still in committee with possible local effects.",
        "introduced": "Early proposal with possible local effects.",
    }
    return _limit_words(stage_summary.get(stage, "May affect constituents if it advances."), 10)


def summarize_finance_alignment(constituent_share: float | None, pac_share: float | None) -> str:
    if constituent_share is None or pac_share is None:
        return "The funding mix becomes clearer after a full finance refresh."
    if constituent_share >= 0.4 and pac_share <= 0.2:
        return "This funding mix leans toward individual donors."
    if pac_share >= 0.3:
        return "A large share of receipts comes from organized committees."
    return "This funding mix is split between individuals and organized committees."


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


def _limit_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".,") + "."
