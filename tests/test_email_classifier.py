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


def test_attachment_antivirus_scanner_blocks_threats_before_use():
    from fleet.core.document_extractor import parse_uploaded_document
    from fleet.integrations.email_intelligence_proposals import (
        EICAR_SIGNATURE_BYTES,
        scan_email_attachment_security,
    )
    import pytest

    # 1. Clean PDF passes pre-download/pre-use antivirus check
    clean_res = scan_email_attachment_security(
        filename="Stripe_Invoice_INV-2026-10-8941.pdf",
        content_bytes=b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF",
        mime_type="application/pdf",
    )
    assert clean_res["status"] == "CLEAN"
    assert clean_res["safe_to_download"] is True
    assert clean_res["safe_to_use"] is True
    assert clean_res["threat_code"] is None

    # 2. EICAR test virus signature is blocked in memory
    eicar_res = scan_email_attachment_security(
        filename="invoice_copy.pdf",
        content_bytes=EICAR_SIGNATURE_BYTES,
        mime_type="application/pdf",
    )
    assert eicar_res["status"] == "BLOCKED_THREAT"
    assert eicar_res["safe_to_use"] is False
    assert eicar_res["threat_code"] == "EICAR_AV_TEST_SIGNATURE"

    # 3. Double extension / executable spoof is blocked
    exe_res = scan_email_attachment_security(
        filename="Urgent_Invoice.pdf.exe",
        content_bytes=b"hello",
    )
    assert exe_res["status"] == "BLOCKED_THREAT"
    assert exe_res["safe_to_use"] is False

    # 4. Disguised PE/MZ binary inside a .pdf filename is blocked
    mz_res = scan_email_attachment_security(
        filename="Contract_Draft.pdf",
        content_bytes=b"MZ\x90\x00\x03\x00\x00\x00",
    )
    assert mz_res["status"] == "BLOCKED_THREAT"
    assert mz_res["threat_code"] == "DISGUISED_PE_EXECUTABLE"

    # 5. parse_uploaded_document refuses to parse any virus-flagged payload
    with pytest.raises(ValueError, match="Security Antivirus Block"):
        parse_uploaded_document(
            filename="malicious_doc.pdf",
            content_bytes=EICAR_SIGNATURE_BYTES,
        )


def test_email_proposals_unapproved_backlog_and_user_approval_flow(tmp_path):
    from fleet.core.database import FleetDatabase
    from fleet.integrations.email_intelligence_proposals import (
        approve_email_proposal,
        discover_email_and_attachment_proposals,
        reject_email_proposal,
    )

    db = FleetDatabase(db_path=tmp_path / "test_email_proposals.db")
    res = discover_email_and_attachment_proposals(db=db)
    assert res["status"] == "ok"
    assert res["total_proposals"] >= 4
    assert res["unapproved_count"] >= 4
    assert res["clean_attachments_count"] >= 2

    # Verify Unapproved items are registered in feature_backlog
    stats = db.get_feature_backlog_stats()
    assert stats["unapproved"] >= 4
    unapproved_items = db.list_feature_backlog_items(status="Unapproved")
    assert len(unapproved_items) >= 4

    # Approve a track_addition proposal and verify backlog transitions Unapproved -> Completed
    track_prop = next(p for p in res["proposals"] if p["proposal_type"] == "track_addition")
    app_res = approve_email_proposal(proposal_id=track_prop["id"], db=db)
    assert app_res["status"] == "ok"
    assert app_res["backlog_status"] == "Completed"
    assert app_res["implemented"]["action"] == "added_tracking_task"

    # Reject another proposal and verify backlog transitions Unapproved -> Deferred
    other_prop = next(p for p in res["proposals"] if p["id"] != track_prop["id"])
    rej_res = reject_email_proposal(proposal_id=other_prop["id"], db=db)
    assert rej_res["status"] == "ok"
    assert rej_res["backlog_status"] == "Deferred"



