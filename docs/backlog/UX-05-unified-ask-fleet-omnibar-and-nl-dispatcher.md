# ⌨️ UX-05: Unified "Ask Fleet Anything" Omnibar & Cross-Agent Natural-Language Dispatcher

| Attribute | Value |
| :--- | :--- |
| **Feature ID** | `UX-05` |
| **Priority** | 🔴 **P1 (High UX Enhancement — Rank #5)** |
| **UX Impact Score** | **91 / 100** *(Impact: 36/40, Friction Reduction: 23/25, Zero-Token Leverage: 19/20, Speed: 13/15)* |
| **Category** | `UI/UX` & `AI/LLM` |
| **Target Release** | `v2.8.9` |
| **Status** | `🟢 Completed` |
| **Affected Subsystems** | `fleet/core/token_optimizer.py`, `fleet/web/templates/dashboard.html`, `fleet/api/chat_api.py` |

---

## 1. Executive Summary & User Problem Statement

### Current Friction
Currently, AFCC has two separate interaction surfaces:
1. The **Spotlight Command Palette (`Ctrl+K` / `/`)** for navigating to agent tabs or triggering static menu items.
2. The **Chat / Tier-0 Input Box** for asking questions.

When a user wants to perform a quick action on a specific agent (e.g., logging 500ml of water, adding a P1 task, checking today's Samtola workout, or running a RAM cleanup), they either have to switch tabs and find the button, or type into the chat box.

### Proposed UX Transformation
Unify **Spotlight Navigation + `@agent` Slash Commands + Tier-0 Natural-Language Execution + Inline Live Result Cards** into a single **Universal Ask-Fleet Omnibar (`Ctrl+K` or `/`)** modeled after Raycast / Alfred / Linear:
- Type `health` -> Jump to the Health tab.
- Type `@health water +2` or `drank 2 glasses` -> Immediately increments hydration in SQLite and renders an **inline animated confirmation card right inside the Omnibar** without leaving your current tab!
- Type `@discover` -> Shows top recommended new agents from `UX-02`.
- Type `create agent ...` -> Launches `UX-01` Natural-Language Agent Studio with the prompt pre-filled.

---

## 2. Dynamic Agent Intent Registration (`get_omnibar_commands`)

Every plug-and-play `FleetAgent` subclass can optionally expose `get_omnibar_commands(self) -> List[Dict[str, Any]]`:

```python
def get_omnibar_commands(self) -> List[Dict[str, Any]]:
    return [
        {
            "trigger": "water",
            "syntax": "@health water [glasses]",
            "description": "Log glasses of water drank today",
            "task": "log_water",
        },
        {
            "trigger": "workout",
            "syntax": "@health workout done",
            "description": "Mark today's 6-Day Strength Split session complete",
            "task": "complete_workout",
        },
    ]
```

Whenever a new custom agent is installed, its commands are **automatically indexed** in the Omnibar with zero core code changes!

---

## 3. Acceptance Criteria & Verification Plan
- [ ] Pressing `Ctrl+K` or `/` opens the unified Omnibar supporting fuzzy tab navigation, `@agent` command autocomplete, and natural-language Tier-0 execution (`$0.00` tokens).
- [ ] Executing an action renders an instant inline result preview card inside the Omnibar within `< 30ms`.
- [ ] Custom agents automatically appear in `@agent` autocomplete upon registration.

