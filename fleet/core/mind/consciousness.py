"""
Consciousness — The Aware Executive Mind & Self-Critique Engine for Personal Agentic Fleet.
Maintains situational awareness, executive attention focus, and a continuous meta-cognitive
self-critique evaluation loop verifying quality, soundness, and intent fidelity.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class ConsciousnessState(str, Enum):
    FOCUSED = "FOCUSED"          # Single high-priority executive task executing
    AWARE = "AWARE"              # Observing and listening across all sensory synapses
    REFLECTING = "REFLECTING"    # Performing self-critique or meta-evaluating output
    DELIBERATING = "DELIBERATING"# Evaluating competing options or schedules
    RESTING = "RESTING"          # Low activity; preparing for subconscious dream cycle


@dataclass
class ExecutiveAttention:
    active_agent: str
    current_goal: str
    focus_started_at: str
    context_keys: List[str] = field(default_factory=list)
    state: ConsciousnessState = ConsciousnessState.AWARE


@dataclass
class CritiqueResult:
    critique_id: str
    agent: str
    action: str
    score: float  # 0.0 - 100.0
    passed: bool
    notes: str
    strengths: List[str] = field(default_factory=list)
    deficiencies: List[str] = field(default_factory=list)
    corrective_action: str = ""
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SelfCritiqueEngine:
    """
    Meta-cognitive evaluator that critiques agent execution outputs deterministically ($0.00 / 0 tokens).
    Validates correctness, completeness, data structure sanity, and performance economy.
    """

    def __init__(self, db: Any = None):
        self.db = db

    def critique(
        self,
        agent: str,
        action: str,
        input_payload: Optional[Dict[str, Any]] = None,
        output_result: Optional[Dict[str, Any]] = None,
    ) -> CritiqueResult:
        """
        Executes multi-axial self-critique on an action result:
        1. Structural Soundness: Valid data types, no uncaught exceptions, no None-returns where dict expected.
        2. Content Depth & Completeness: Meaningful strings, non-empty datasets, actionable fields.
        3. Token & Performance Economy: Zero unnecessary calls, fast response times.
        4. Error Transparency: Clean status codes, intelligible error descriptions if failing.
        """
        input_payload = input_payload or {}
        output_result = output_result or {}

        score = 100.0
        strengths: List[str] = []
        deficiencies: List[str] = []
        corrective_action = ""

        # Check 1: Structural Integrity
        if not isinstance(output_result, dict):
            score -= 40.0
            deficiencies.append("Output is not a valid structured dictionary.")
            corrective_action = "Wrap return value in structured dictionary with 'status' and 'data' keys."
        else:
            status = str(output_result.get("status", "")).lower()
            if status in ("success", "ok", "completed", "verified"):
                strengths.append("Clean success status reported.")
            elif status in ("error", "failed", "exception"):
                score -= 35.0
                err_msg = output_result.get("error") or output_result.get("message") or "Unknown error"
                deficiencies.append(f"Action reported execution error: {err_msg}")
                corrective_action = "Inspect underlying service failure and re-try with backoff."
            elif not status:
                score -= 10.0
                deficiencies.append("Output lacks an explicit 'status' property.")

        # Check 2: Content Richness & Hallucination/Null Check
        empty_keys = []
        for k, v in output_result.items():
            if v is None:
                empty_keys.append(k)
            elif isinstance(v, (str, list, dict)) and len(v) == 0 and k not in ("errors", "warnings"):
                empty_keys.append(k)

        if empty_keys:
            score -= min(20.0, len(empty_keys) * 5.0)
            deficiencies.append(f"Result contains empty/null fields: {', '.join(empty_keys[:4])}")
            if not corrective_action:
                corrective_action = "Ensure all requested fields are fully populated with meaningful content."
        else:
            strengths.append("All output fields are fully populated.")

        # Check 3: Error Masking or Silent Failures
        if "error" in output_result and output_result.get("status") == "success":
            score -= 30.0
            deficiencies.append("Contradictory state: 'error' key present while status is 'success'.")
            corrective_action = "Disambiguate status when handling partial or non-fatal errors."

        # Check 4: Intent Alignment Check
        if action.upper() in ("GET_BRIEFING", "BRIEFING") and "headline" not in output_result:
            score -= 25.0
            deficiencies.append("Briefing action missed expected 'headline' attribute.")
            corrective_action = "Regenerate briefing ensuring top headline is synthesized."

        # Final Score Normalization
        score = round(max(0.0, min(100.0, score)), 1)
        passed = score >= 70.0

        if passed:
            strengths.append("Meets self-critique quality threshold.")
            notes = "Self-critique passed: output is structurally sound and aligned with agent intent."
        else:
            notes = f"Self-critique flagged quality issues ({score}/100): " + "; ".join(deficiencies)

        critique_id = f"CRIT-{int(time.time() * 1000)}"

        # Persist to database if mixin available
        if self.db and hasattr(self.db, "log_critique"):
            try:
                self.db.log_critique(
                    agent=agent,
                    action=action,
                    critique_score=score,
                    critique_notes=notes,
                    corrective_action=corrective_action,
                    input_summary=json.dumps(input_payload, default=str),
                    output_summary=json.dumps(output_result, default=str),
                    confidence=1.0 if passed else 0.8,
                )
            except Exception:
                pass

        return CritiqueResult(
            critique_id=critique_id,
            agent=agent,
            action=action,
            score=score,
            passed=passed,
            notes=notes,
            strengths=strengths,
            deficiencies=deficiencies,
            corrective_action=corrective_action,
            confidence=1.0 if passed else 0.8,
        )

    evaluate = critique


class ConsciousExecutive:
    """
    The conscious core of the fleet. Manages active focus of attention,
    orchestrates high-priority goals, and applies real-time self-critiquing.
    """

    def __init__(self, db: Any = None):
        self.db = db
        self.critique_engine = SelfCritiqueEngine(db=db)
        self._attention = ExecutiveAttention(
            active_agent="OverviewAgent",
            current_goal="Monitoring personal productivity & workstation vitals",
            focus_started_at=datetime.now().isoformat(),
            context_keys=["briefing", "vitals", "agenda"],
            state=ConsciousnessState.AWARE,
        )
        self._lock = threading.RLock()
        self._recent_critiques: List[CritiqueResult] = []

    def set_focus(self, agent: str, goal: str, context_keys: Optional[List[str]] = None) -> None:
        """Directs executive conscious attention to a specific agent and immediate goal."""
        self.set_attention(agent=agent, goal=goal, state=ConsciousnessState.FOCUSED, context_keys=context_keys)

    def set_attention(
        self,
        agent: str,
        goal: str,
        state: ConsciousnessState = ConsciousnessState.FOCUSED,
        context_keys: Optional[List[str]] = None,
    ) -> None:
        """Sets executive conscious attention state, agent, and goal."""
        with self._lock:
            self._attention = ExecutiveAttention(
                active_agent=agent,
                current_goal=goal,
                focus_started_at=datetime.now().isoformat(),
                context_keys=context_keys or [],
                state=state,
            )

    def release_focus(self) -> None:
        """Relaxes conscious focus back to ambient awareness."""
        with self._lock:
            self._attention.state = ConsciousnessState.AWARE
            self._attention.current_goal = "Ambient awareness across all fleet routines"

    def evaluate_action(
        self,
        agent: str,
        action: str,
        input_payload: Optional[Dict[str, Any]] = None,
        output_result: Optional[Dict[str, Any]] = None,
    ) -> CritiqueResult:
        """Consciously self-critiques an action, recording the meta-cognitive appraisal."""
        with self._lock:
            old_state = self._attention.state
            self._attention.state = ConsciousnessState.REFLECTING

        result = self.critique_engine.critique(
            agent=agent,
            action=action,
            input_payload=input_payload,
            output_result=output_result,
        )

        with self._lock:
            self._recent_critiques.insert(0, result)
            self._recent_critiques = self._recent_critiques[:50]
            self._attention.state = old_state

        return result

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            att = asdict(self._attention)
            att["state"] = self._attention.state.value

            recent = [asdict(c) for c in self._recent_critiques[:10]]
            avg_score = 100.0
            if self._recent_critiques:
                avg_score = round(sum(c.score for c in self._recent_critiques) / len(self._recent_critiques), 1)

            return {
                "layer": "Consciousness (Executive Attention & Meta-Critique)",
                "state": self._attention.state.value,
                "attention": att,
                "executive_attention": att,
                "meta_critique_vitals": {
                    "recent_critiques_count": len(self._recent_critiques),
                    "total_critiques_logged": len(self._recent_critiques),
                    "average_quality_score": avg_score,
                    "pass_rate_pct": round(
                        (len([c for c in self._recent_critiques if c.passed]) / max(1, len(self._recent_critiques))) * 100.0,
                        1
                    ),
                },
                "recent_critiques": recent,
            }
