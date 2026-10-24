"""
Deterministic Zero-Token Email Classifier for Personal Agentic Fleet.
Classifies emails into 5 folders:
  0) Meetings
  1) Respond
  2) Note
  3) FYI
  4) Ignore

Strictly enforces Fleet Governance & Zero-Token Mandate:
  - 100% Pure Deterministic Logic & Regex Heuristics (0 Tokens / $0.00).
  - Tokens are strictly reserved for code enhancement tasks only.
  - Email intelligence guarantees 0 token consumption on every refresh.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

CATEGORIES = {
    0: "Meetings",
    1: "Respond",
    2: "Note",
    3: "FYI",
    4: "Ignore"
}

CATEGORY_LABEL_MAP = {
    0: "Fleet/0-Meetings",
    1: "Fleet/1-Respond",
    2: "Fleet/2-Note",
    3: "Fleet/3-FYI",
    4: "Fleet/4-Ignore"
}


# --- Tier 0: Deterministic Patterns (0 Tokens) ---

# 0) Meetings Patterns
MEETING_SENDERS = [
    r"calendar-notification@google\.com",
    r"no-reply@zoom\.us",
    r"scheduling@calendly\.com",
    r"invitations@linkedin\.com"
]
MEETING_SUBJECTS = [
    r"\binvitation\b", r"\bupdated invitation\b", r"\baccepted\b", r"\bdeclined\b",
    r"\btentative\b", r"\bcanceled event\b", r"\bmeeting\b", r"\bzoom meeting\b",
    r"\bgoogle meet\b", r"\brsvp\b", r"\bschedule a time\b"
]

# 2) Note Patterns (Receipts, Invoices, Financials, Bookings, Tickets)
NOTE_SUBJECTS = [
    r"\breceipt\b", r"\border confirmation\b", r"\binvoice\b", r"\be-?ticket\b",
    r"\bboarding pass\b", r"\bbooking confirmation\b", r"\bflight confirmation\b",
    r"\bhotel reservation\b", r"\bstatement\b", r"\bpayment confirmation\b",
    r"\bshipped\b", r"\btracking number\b", r"\btax document\b", r"\bw-2\b",
    r"\bsecurity alert\b", r"\bverification code\b", r"\bone-time passcode\b", r"\botp\b"
]
NOTE_SENDERS = [
    r"@amazon\.", r"@apple\.com", r"@uber\.com", r"@swiggy\.in", r"@zomato\.com",
    r"@chase\.com", r"@bankofamerica\.com", r"@paypal\.com", r"@stripe\.com"
]

# 4) Ignore Patterns (Promotions, Cold Marketing, Social Media)
IGNORE_SENDERS = [
    r"@marketing\.", r"@promo\.", r"@newsletter\.", r"@e\.", r"@em\.", r"@mail\.",
    r"deals@", r"offers@", r"promotions@", r"marketing@", r"updates@linkedin\.com"
]
IGNORE_SUBJECTS = [
    r"\bdiscount\b", r"\b%\s*off\b", r"\bsale\b", r"\bfree shipping\b",
    r"\bdeal of the day\b", r"\blimited time offer\b", r"\bexclusive invite to shop\b",
    r"\bdon't miss out\b", r"\bblack friday\b", r"\bcyber monday\b", r"\bcoupon\b"
]

# 3) FYI Patterns (Newsletters, Product Updates, Status Reports)
FYI_SUBJECTS = [
    r"\bweekly digest\b", r"\bnewsletter\b", r"\bmonthly recap\b", r"\broundup\b",
    r"\brelease notes\b", r"\bproduct update\b", r"\bchangelog\b", r"\bcommunity digest\b"
]


def classify_deterministic(email_meta: Dict[str, Any]) -> Optional[Tuple[int, str]]:
    """
    Tier 0: Pure regex & header evaluation (0 tokens).
    Returns (category_id, reason) if confident, or None if ambiguous.
    """
    subject = email_meta.get("subject", "").lower()
    sender = email_meta.get("from", "").lower()
    snippet = email_meta.get("snippet", "").lower()
    mime_type = email_meta.get("mime_type", "").lower()
    has_calendar = email_meta.get("has_calendar_part", False)

    # 1. Check Meetings (Priority 1)
    if has_calendar or "text/calendar" in mime_type:
        return 0, "Calendar MIME/Attachment detected"
    for pattern in MEETING_SENDERS:
        if re.search(pattern, sender):
            return 0, f"Meeting sender pattern: {pattern}"
    for pattern in MEETING_SUBJECTS:
        if re.search(pattern, subject):
            return 0, f"Meeting subject pattern: {pattern}"

    # 2. Check Note (Receipts / Financials / Bookings)
    for pattern in NOTE_SUBJECTS:
        if re.search(pattern, subject):
            return 2, f"Note subject pattern: {pattern}"
    for pattern in NOTE_SENDERS:
        if re.search(pattern, sender):
            # If from financial/commerce and mentions order/charge/thank you
            if any(k in subject or k in snippet for k in ["order", "payment", "your", "charge", "thank you", "delivery"]):
                return 2, f"Commerce sender notification: {pattern}"

    # 3. Check Ignore (Promotions / Sales / Marketing)
    for pattern in IGNORE_SUBJECTS:
        if re.search(pattern, subject):
            return 4, f"Promotional subject pattern: {pattern}"
    for pattern in IGNORE_SENDERS:
        if re.search(pattern, sender):
            return 4, f"Marketing sender pattern: {pattern}"

    # 4. Check FYI (Newsletters / Company Digests)
    for pattern in FYI_SUBJECTS:
        if re.search(pattern, subject):
            return 3, f"Digest/Newsletter pattern: {pattern}"

    # 5. Check Respond Heuristics (Direct inquiries)
    # Direct 1-on-1 recipient without mailing list headers + interrogative phrasing
    is_direct = email_meta.get("is_direct_to", False)
    has_question = "?" in subject or any(q in snippet for q in ["can you", "could you", "please let me know", "thoughts?", "when are you"])
    if is_direct and has_question and not re.search(r"\bno-?reply\b", sender):
        return 1, "Direct personal email with inquiry"

    return None


class EmailClassifier:
    """
    100% Deterministic Tier 0 Email Classifier (0 Tokens / $0.00).
    Resolves all classifications via deterministic rule sets and semantic heuristics.
    Tokens are strictly restricted to code enhancement only.
    """
    def __init__(self):
        pass

    def classify_single(self, email_meta: Dict[str, Any]) -> Tuple[int, str]:
        """Classify a single email deterministically with 0 tokens spent."""
        # Tier 0 Deterministic exact regex/header pattern matching
        deterministic = classify_deterministic(email_meta)
        if deterministic is not None:
            return deterministic

        # Tier 0 Deterministic Semantic Heuristics (0 Tokens)
        subject = email_meta.get("subject", "").lower()
        sender = email_meta.get("from", "").lower()
        snippet = email_meta.get("snippet", "").lower()

        if "?" in subject or "?" in snippet or "please" in snippet:
            return 1, "Deterministic Heuristic: Inferred action request (Respond)"
        elif any(w in subject for w in ["update", "announcement", "info", "notice"]):
            return 3, "Deterministic Heuristic: Inferred informational (FYI)"
        elif any(w in sender for w in ["noreply", "no-reply", "notification", "system"]):
            return 3, "Deterministic Heuristic: Inferred automated notification (FYI)"
        else:
            # Default safest category is FYI so nothing is lost
            return 3, "Deterministic Heuristic: General inbox default (FYI)"

    def classify_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify a list of emails with category ID and label name."""
        results = []
        for em in emails:
            cat_id, reason = self.classify_single(em)
            results.append({
                "id": em.get("id"),
                "subject": em.get("subject", "(No Subject)"),
                "from": em.get("from", ""),
                "snippet": em.get("snippet", ""),
                "body": em.get("body") or em.get("snippet", ""),
                "category_id": cat_id,
                "category_name": CATEGORIES[cat_id],
                "label": CATEGORY_LABEL_MAP[cat_id],
                "reason": reason,
                "can_unsubscribe": bool(em.get("can_unsubscribe", False)),
                "unsubscribe_url": em.get("unsubscribe_url"),
                "unsubscribe_type": em.get("unsubscribe_type", "http"),
                "unsubscribed": bool(em.get("unsubscribed", False))
            })
        return results

