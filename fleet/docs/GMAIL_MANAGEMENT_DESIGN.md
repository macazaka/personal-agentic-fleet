# Design Document: Automated Gmail Email Management & Classification

**System**: Personal Agentic Fleet  
**Component**: `GmailManager` (`EmailWorker` + `DeterministicEventBus` + `FastMCP`)  
**Scope**: Classify all emails from this month and last month into 5 specific categories, running daily at an optimal frequency.

---

## 1. Executive Summary & Objectives

The goal is to provide autonomous, zero-friction inbox organization for the user's Gmail account by:
1. **Filtering & Scope**: Processing all messages spanning the current month and the prior month (`after:YYYY/MM/01`).
2. **5-Folder Classification Taxonomy**:
   - `0) Meetings`
   - `1) Respond`
   - `2) Note`
   - `3) FYI`
   - `4) Ignore`
3. **Execution Schedule**: Running autonomously on the laptop at a relevant, battery- and quota-friendly frequency (2-hour active pulses + twice-daily deep catch-up syncs).
4. **Cost & Token Prime Directive**: Resolving 65%+ of classifications using **Tier 0 Deterministic Heuristics (0 tokens)**, and batching ambiguous emails into ultra-lean payloads using `flash_lite`.

---

## 2. System Architecture

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      Gmail API (OAuth 2.0 / REST)                      │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Query: after:YYYY/MM/01 -label:Fleet*
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │               Email Intake & Pre-Filter Pipeline                       │
 │      • Incremental delta fetch (skips already-classified emails)       │
 │      • Header metadata extraction (From, Subject, Snippet, Headers)    │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
 ┌───────────────────────────────────┐               ┌───────────────────┐
 │ Tier 0: Deterministic Rule Engine │ (65% match)   │ Tier 1: LLM Batch │ (35%)
 │  • Calendar MIME / .ics           │ ────────────► │   Classifier      │
 │  • List-Unsubscribe / Newsletters │ (0 Tokens)    │ • Batched headers │
 │  • Receipts / Invoices keywords   │               │ • flash_lite JSON │
 └─────────────────┬─────────────────┘               └─────────┬─────────┘
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                Label Dispatcher & Batch Modification                   │
 │           Applies Gmail Labels via users.messages.batchModify          │
 └───────────────────────────────────────┬────────────────────────────────┘
                                         │
 ┌───────────────────────────────────────▼────────────────────────────────┐
 │        FleetDaemon (Scheduler) & FastMCP Tool Registration             │
 │  • 2-Hour Active Pulse Check      • Morning/Evening Sync               │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Classification Taxonomy & Decision Rules

| Label / Folder | Criteria & Semantic Intent | Deterministic Heuristic Indicators (Tier 0) | LLM Context (Tier 1) |
| :--- | :--- | :--- | :--- |
| **`0) Meetings`** | Calendar invitations, RSVPs, reschedule requests, Zoom/Meet links, call coordinates. | `Content-Type: text/calendar`, presence of `.ics` attachments, sender `calendar-notification@google.com`, subjects like `Invitation:`, `Accepted:`, `Updated invitation:`. | Direct emails proposing meeting times, coffee chats, or interview coordination. |
| **`1) Respond`** | Action-required personal/work emails, direct inquiries, approvals, urgent requests. | Direct 1-to-1 recipient (User in `To:`, not `Bcc:`), no `List-Unsubscribe` header, high importance flags. | Questions asking for user feedback, deliverables, decisions, or follow-ups. |
| **`2) Note`** | Receipts, financial statements, travel itineraries, order confirmations, account security pins. | Subject contains `Receipt`, `Order #`, `Invoice`, `Booking confirmation`, `e-Ticket`, `Statement`, `Tracking`. Senders from banks, airlines, retail. | Reference documentation, product manuals, account credential logs, legal disclosures. |
| **`3) FYI`** | Company/team announcements, informational digests, software release notes, non-urgent updates. | Team-wide mailing lists, project updates (Jira, GitHub, Slack digests) where user is not directly tagged. | Industry newsletters, general informational broadcasts where no response is needed. |
| **`4) Ignore`** | Marketing cold emails, retail promos, social media alerts, automated spam. | `category:promotions`, `category:social`, senders from marketing domains, unsubscribe links with generic sales copy. | Unsolicited vendor pitches, marketing blitzes, webinars, junk. |

---

## 4. Query & Lookback Window (This Month & Last Month)

To satisfy the requirement of covering **both this month and last month**:

1. **Dynamic Start Date**:
   ```python
   # If current date is Oct 13, 2026:
   # Start date = Sept 01, 2026
   start_of_last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
   query_date = start_of_last_month.strftime("%Y/%m/%d")
   ```
2. **Incremental Query Optimization**:
   To prevent re-processing emails that have already been classified:
   ```
   after:{query_date} -label:"Fleet/0-Meetings" -label:"Fleet/1-Respond" -label:"Fleet/2-Note" -label:"Fleet/3-FYI" -label:"Fleet/4-Ignore"
   ```
   *Benefit*: After the initial historical backfill, daily scans process only new unclassified arrivals (~10–30 emails/day), saving bandwidth and processing time.

---

## 5. Cost & Token Optimization Strategy (Fleet Governance Compliance)

Under our **Prime Directive (Lowest Token Cost First)**:

1. **Payload Minimization**:
   - Never download or pass full email bodies, HTML markup, or base64 attachments to an LLM.
   - Extract only:
     ```json
     {
       "id": "18a1b2c3d4",
       "from": "Alex Rivera <alex@work.com>",
       "subject": "Can you review the Q3 budget deck by 3 PM?",
       "snippet": "Hey, please take a look at slides 4-7 and let me know if..."
     }
     ```
2. **Tier 0 Deterministic Pass (0 Tokens / $0.00)**:
   - Evaluated locally in Python using regex and header inspection.
   - Catches 60–70% of inbound volume (calendar invites, promos, automated receipts).
3. **Batch Classification (Tier 1)**:
   - Remaining unclassified emails are grouped into batches of **15 emails per prompt**.
   - Structured JSON response:
     ```json
     [
       {"id": "18a1b2c3d4", "category": 1},
       {"id": "18a1b2c3d5", "category": 3}
     ]
     ```
   - **Model**: `gemini-2.0-flash-lite` (~40 tokens per classified message).

---

## 6. Execution Cadence & Scheduling

### Recommended Daily Frequency:
- **Active Hours Pulse (Every 2 Hours, 08:00 – 18:00)**:
  - Scans new incoming emails from the last 2 hours.
  - Keeps the `1) Respond` and `0) Meetings` folders fresh during the workday.
  - Takes < 2 seconds to run via incremental delta query.
- **Deep Reconciliation Batch (Twice Daily)**:
  - **08:15 AM**: Pre-morning-briefing scan (ensures morning briefing has accurate counts).
  - **08:15 PM**: Evening reconciliation scan.
- **On-Demand Trigger**:
  - Available via FastMCP tool (`fleet_classify_emails`) or Web Dashboard button.

---

## 7. Component Architecture in `fleet/`

We will implement this by adding:

```
fleet/
├── integrations/
│   ├── __init__.py
│   ├── gmail_client.py       # OAuth2 handler, label management, batch fetch/modify
│   └── email_classifier.py   # Deterministic heuristics + batched flash_lite classifier
├── core/
│   └── event_bus.py          # Adds 'email' target worker to DeterministicEventBus
├── daemon.py                 # Scheduled 2-hour pulse and 8:15 AM/PM triggers
└── mcp_server.py             # Exposes fleet_sync_and_classify_emails() tool
```

---

## 8. Safety & User Autonomy (User-Choice Rule)

1. **Non-Destructive Labeling**:
   - The system **applies labels** (`Fleet/0-Meetings`, etc.). It **never deletes or marks emails as spam**.
   - User's primary `Inbox` can remain intact, or optional auto-archive can be enabled per category.
2. **Reviewable & Reversible**:
   - If an email is miscategorized, changing the label in Gmail or clicking the undo button in the Web Dashboard updates the fleet's memory.
3. **Local Credentials Storage**:
   - OAuth tokens stored locally in `fleet/data/gmail_token.json` (gitignored).

---

## 9. Verification & Rollout Plan

1. **Phase 1: OAuth Setup & Gmail Connection**:
   - User provides `credentials.json` (Google Cloud Desktop Client).
   - Test basic connection and verify label creation.
2. **Phase 2: Dry-Run Classification Test**:
   - Fetch last 50 emails from current/last month.
   - Run Tier 0 heuristics + Tier 1 classifier in dry-run mode (print preview of categories without modifying Gmail).
3. **Phase 3: Live Batch Execution**:
   - Apply labels to all emails across this month and last month.
4. **Phase 4: Daemon Activation**:
   - Enable automated 2-hour and morning/evening cron in `fleet/daemon.py`.

