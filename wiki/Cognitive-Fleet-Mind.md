# Cognitive Fleet Mind

The **Cognitive Fleet Mind** is the autonomic nervous system and conscious intelligence layer of the Personal Agentic Fleet. Inspired by organic cognitive science, it coordinates deterministic execution, active self-critique, background dream consolidation, and ethical tenet adherence.

---

## The 4 Organic Layers

```
+-------------------------------------------------------------------+
| Layer 4: Fleet Soul (Moral Compass & Tenet Preservation)          |
| - Sovereign Privacy Tenet: Strict local boundary enforcement      |
| - Zero-Token Frugality Tenet: 100% Tier 0 local compute default   |
| - User-Choice First Tenet: Zero paternalistic overrides           |
+-------------------------------------------------------------------+
                                  ^
                                  | Tenet Verification
+-------------------------------------------------------------------+
| Layer 3: Subconscious Mind & Dreaming Engine                      |
| - Periodic Episodic Log Mining: Mines error patterns & friction  |
| - Dream Consolidation: Derives proactive habits & fixes           |
| - Autonomous Auto-Healing: Triggers immunological repair recipes  |
+-------------------------------------------------------------------+
                                  ^
                                  | Anomaly Telemetry
+-------------------------------------------------------------------+
| Layer 2: Conscious Executive & Active Self-Critique Engine        |
| - Dynamic Attention Focus: Tracks currently active cognitive task |
| - Multi-Axial Critique Rubric: Soundness, Depth, Token Efficiency |
| - Conscious Score Target: Mandates >= 85 prior to committing      |
+-------------------------------------------------------------------+
                                  ^
                                  | Synaptic Events
+-------------------------------------------------------------------+
| Layer 1: Physical Brain (Synaptic Bus & Epistemic Memory)         |
| - Ephemeral Synaptic Bus: Sub-millisecond cross-agent messaging   |
| - Epistemic SQLite WAL Memory: High-concurrency durable facts     |
| - Autonomic Reflex Arc: Sub-second recovery on unexpected faults  |
+-------------------------------------------------------------------+
```

---

## Epistemic Memory & Synaptic Events

Agents interact with the Cognitive Mind by emitting synaptic events:

```python
from fleet.core.mind import get_fleet_mind

mind = get_fleet_mind()

# Emit an observation event
mind.brain.emit_synaptic_event(
    source="gmail_agent",
    event_type="email_classified",
    payload={"category": "finance", "sender": "bank@example.com"}
)

# Record durable fact in epistemic memory
mind.brain.record_fact("user_timezone", "America/New_York", confidence=1.0)
```

---

## Conscious Self-Critique Rubric

Before submitting actions or saving state, the Consciousness engine evaluates the result across three axes:

1. **Soundness**: Verifies schema compliance, deterministic assertions, and zero errors.
2. **Depth / Relevance**: Checks that the result directly answers the task objective.
3. **Frugality / Token Efficiency**: Asserts that no unnecessary LLM tokens were consumed ($0.00 Tier 0 compliance).

If the aggregate score is below 85, the action is rejected or routed to the self-healing reflex arc.
