"""Unit tests for fleet.integrations.email_classifier."""
from fleet.integrations.email_classifier import (
    CATEGORIES,
    CATEGORY_LABEL_MAP,
    EmailClassifier,
    classify_deterministic,
)


def test_classify_deterministic_all_categories():
    # 0) Meetings
    c0_mime, _ = classify_deterministic({"mime_type": "text/calendar", "subject": "Quarterly Planning"})
    assert c0_mime == 0
    c0_cal, _ = classify_deterministic({"has_calendar_part": True})
    assert c0_cal == 0
    c0_sender, _ = classify_deterministic({"from": "scheduling@calendly.com", "subject": "New Call"})
    assert c0_sender == 0
    c0_subj, _ = classify_deterministic({"subject": "Updated Invitation: Sprint Review"})
    assert c0_subj == 0

    # 2) Note
    c2_subj, _ = classify_deterministic({"subject": "Your flight confirmation and booking"})
    assert c2_subj == 2
    c2_sender, _ = classify_deterministic({"from": "order-update@amazon.com", "subject": "Package arrived", "snippet": "thank you for shopping"})
    assert c2_sender == 2


    # 4) Ignore
    c4_subj, _ = classify_deterministic({"subject": "Exclusive 50% discount and sale"})
    assert c4_subj == 4
    c4_sender, _ = classify_deterministic({"from": "deals@retailer.com", "subject": "Check this out"})
    assert c4_sender == 4

    # 3) FYI
    c3_subj, _ = classify_deterministic({"subject": "Monthly recap and product update"})
    assert c3_subj == 3

    # 1) Respond
    c1_direct, _ = classify_deterministic({
        "from": "colleague@work.com",
        "subject": "Can we talk?",
        "is_direct_to": True
    })
    assert c1_direct == 1

    # Ambiguous
    assert classify_deterministic({"subject": "Random note", "from": "someone@work.com"}) is None


def test_email_classifier_tier1_fallbacks_and_batch():
    classifier = EmailClassifier()

    # Tier 1 fallback with question
    cat, r = classifier.classify_single({"subject": "FYI discussion", "snippet": "Can you check this?"})
    assert cat == 1

    # Tier 1 fallback with announcement
    cat, r = classifier.classify_single({"subject": "Company notice"})
    assert cat == 3

    # Tier 1 fallback with automated sender
    cat, r = classifier.classify_single({"from": "system-notifications@corp.local"})
    assert cat == 3

    # Tier 1 fallback default
    cat, r = classifier.classify_single({"subject": "Random thought", "from": "friend@personal.com"})
    assert cat == 3

    # Batch classification
    batch = classifier.classify_batch([
        {"id": "m1", "subject": "Zoom Meeting Invite", "has_calendar_part": True, "can_unsubscribe": False},
        {
            "id": "m2",
            "subject": "Invoice for Service",
            "from": "billing@stripe.com",
            "snippet": "payment",
            "can_unsubscribe": True,
            "unsubscribe_url": "https://stripe.com/unsub",
            "unsubscribe_type": "http",
            "unsubscribed": True
        },
    ])
    assert len(batch) == 2
    assert batch[0]["can_unsubscribe"] is False
    assert batch[0]["unsubscribed"] is False
    assert batch[1]["can_unsubscribe"] is True
    assert batch[1]["unsubscribe_url"] == "https://stripe.com/unsub"
    assert batch[1]["unsubscribe_type"] == "http"
    assert batch[1]["unsubscribed"] is True

    # Commerce sender without order/payment keywords falls through
    res_fall = classify_deterministic({"from": "order-update@amazon.com", "subject": "Hello", "snippet": "Random"})
    assert res_fall is None


