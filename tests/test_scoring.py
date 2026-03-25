from app.models import ActivitySummary, BillRecord, PromiseItem
from app.services.scoring import compute_delivery_score, compute_keeps_promises_score, summarize_bill_impact


def test_compute_delivery_score_matches_policy_areas():
    promises = [
        PromiseItem(
            title="Jobs & Economy",
            description="Jobs promise",
            topic="Jobs & Economy",
            source_label="manual",
            confidence=0.9,
            provenance="manual",
        )
    ]
    activity = ActivitySummary(
        recent_bills=[
            BillRecord(
                title="Manufacturing credit",
                bill_number="HR 1",
                congress=119,
                policy_area="Economics and Public Finance",
                latest_action_text="Passed House",
                stage="passed",
                stage_weight=8.0,
                sponsorship="sponsored",
            )
        ]
    )

    score = compute_delivery_score(promises, activity)
    assert score.overall_score > 0
    assert score.topic_scores[0].matched_actions[0].bill_number == "HR 1"


def test_keeps_promises_score_is_separate_from_delivery_score():
    promises = [
        PromiseItem(
            title="Jobs & Economy",
            description="Jobs promise",
            topic="Jobs & Economy",
            source_label="manual",
            confidence=0.9,
            provenance="manual",
        ),
        PromiseItem(
            title="Healthcare",
            description="Health promise",
            topic="Healthcare",
            source_label="manual",
            confidence=0.9,
            provenance="manual",
        ),
    ]
    activity = ActivitySummary(
        recent_bills=[
            BillRecord(
                title="Manufacturing credit",
                bill_number="HR 1",
                congress=119,
                policy_area="Economics and Public Finance",
                latest_action_text="Passed House",
                stage="passed",
                stage_weight=8.0,
                sponsorship="sponsored",
            )
        ]
    )

    keeps_promises = compute_keeps_promises_score(promises, activity)
    delivery = compute_delivery_score(promises, activity)

    assert keeps_promises == 50
    assert delivery.overall_score != keeps_promises


def test_bill_impact_summary_is_short():
    bill = BillRecord(
        title="HSA's For All Act",
        bill_number="HR 7681",
        congress=119,
        policy_area="Taxation",
        latest_action_text="Referred to committee",
        stage="committee",
        stage_weight=2.0,
        sponsorship="sponsored",
    )

    summary = summarize_bill_impact(bill)
    assert len(summary.split()) <= 10
    assert summary
