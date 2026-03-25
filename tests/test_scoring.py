from app.models import ActivitySummary, BillRecord, PromiseItem
from app.services.scoring import compute_delivery_score


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
