# 🧩 UX-09: Pin-to-Overview Micro-Widgets & Customizable Executive Bento Grid

| Attribute | Value |
| :--- | :--- |
| **Feature ID** | `UX-09` |
| **Priority** | 🟡 **P2 (Medium UX Enhancement — Rank #9)** |
| **UX Impact Score** | **83 / 100** *(Impact: 33/40, Friction Reduction: 20/25, Zero-Token Leverage: 18/20, Speed: 12/15)* |
| **Category** | `UI/UX` |
| **Target Release** | `v3.0.0` |
| **Status** | `Idea` |
| **Affected Subsystems** | `fleet/core/base_agent.py`, `fleet/agents/overview/ui/panel.html`, `fleet/web/templates/dashboard.html` |

---

## 1. Executive Summary & User Problem Statement

### Current Friction
As a user's fleet grows to 10, 20, or 50+ custom agents, each agent has its own full tab. However, during daily operations, the user often wants a **single customizable "Cockpit" screen** showing only the top 1 metric and top 1 button from their 6–8 favorite agents side by side (e.g., *Hydration Glass Counter* + *Today's Mudgal/Samtola Split* + *RAM Free Button* + *01-Focus Unread Count* + *Custom Crypto/Git Watcher Card*).

### Proposed UX Transformation
Allow every `FleetAgent` to expose a compact **Micro-Widget Specification (`get_micro_widget()`)** and add a **"📌 Pin Widget to Overview"** button on every agent header:
-Pinned micro-widgets render in a responsive **Customizable Bento Grid** at the top of the `Overview` tab.
- Users can reorder tiles (`1x1` compact pill or `2x1` action card) or unpin them anytime, persisted in `fleet.yaml` (`pinned_widgets`).

---

## 2. Declarative `get_micro_widget()` Contract on `FleetAgent`

```python
class FleetAgent:
    def get_micro_widget(self) -> Dict[str, Any]:
        """Return a compact 1x1 or 2x1 Bento tile for the Overview cockpit."""
        return {
            "agent_id": self.id,
            "title": self.name,
            "icon": self.icon,
            "primary_metric": "Ready",
            "secondary_label": "Status",
            "quick_action": {
                "label": "▶ Run",
                "task": "default",
            },
        }
```

---

## 3. Acceptance Criteria & Verification Plan
- [ ] `GET /api/overview/widgets` aggregates `get_micro_widget()` payloads for all user-pinned agents in `< 15ms`.
- [ ] Every agent tab header includes a `📌 Pin to Cockpit` toggle button.

