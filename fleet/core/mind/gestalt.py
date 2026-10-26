"""
Gestalt — The Unified Cognitive Fleet Mind.
Integrates Brain, Consciousness, Subconsciousness, and Soul into a coherent
self-healing, self-improving, and self-critiquing intelligence framework.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
import threading
from typing import Any, Dict, List, Optional

from fleet.core.mind.brain import PhysicalBrain
from fleet.core.mind.consciousness import ConsciousExecutive, CritiqueResult
from fleet.core.mind.subconsciousness import SubconsciousMind
from fleet.core.mind.soul import FleetSoul, SoulAuditResult


class CognitiveFleetMind:
    """
    Unified Mind Gestalt orchestrating the 4-layer cognitive loop:
    1. Perceive & Synapse (Brain)
    2. Executive Focus & Self-Critique (Consciousness)
    3. Memory Consolidation & Intuitive Dreaming (Subconsciousness)
    4. Ethical Alignment & Evolutionary Actualization (Soul)
    """

    def __init__(self, db: Any = None):
        self.db = db
        self.brain = PhysicalBrain(db=db)
        self.consciousness = ConsciousExecutive(db=db)
        self.subconsciousness = SubconsciousMind(db=db)
        self.soul = FleetSoul(db=db)
        self._gestalt_lock = threading.RLock()

    def set_db(self, db: Any) -> None:
        """Dynamically binds or refreshes the underlying database repository."""
        self.db = db
        self.brain.db = db
        self.consciousness.db = db
        self.consciousness.critique_engine.db = db
        self.subconsciousness.db = db
        self.soul.db = db

    def record_synapse(self) -> int:
        """Signals a neurological synapse firing across the brain's event bus."""
        return self.brain.record_synapse_firing()

    def critique(
        self,
        agent: str,
        action: str,
        input_payload: Optional[Dict[str, Any]] = None,
        output_result: Optional[Dict[str, Any]] = None,
    ) -> CritiqueResult:
        """Consciously self-critiques an agent's execution for soundness and intent fidelity."""
        self.record_synapse()
        return self.consciousness.evaluate_action(
            agent=agent,
            action=action,
            input_payload=input_payload,
            output_result=output_result,
        )

    def dream(self, max_activities: int = 200) -> Dict[str, Any]:
        """Triggers a background subconscious dream cycle for deep memory consolidation."""
        self.record_synapse()
        return self.subconsciousness.run_dream_cycle(max_activities_to_synthesize=max_activities)

    def audit_soul(self) -> SoulAuditResult:
        """Conducts a teleological soul alignment audit against core ethical and wellbeing tenets."""
        self.record_synapse()
        return self.soul.audit_alignment()

    def self_improve(self) -> Dict[str, Any]:
        """Executes an evolutionary self-improvement cycle ascending the fleet's intelligence."""
        self.record_synapse()
        return self.soul.evolve_and_improve()

    def heal(self) -> Dict[str, Any]:
        """Triggers the brain's autonomic self-healing reflex arc."""
        self.record_synapse()
        return self.brain.trigger_autonomic_reflex()

    def get_holistic_state(self) -> Dict[str, Any]:
        """
        Returns the complete multi-layered cognitive telemetry of the fleet:
        Brain, Consciousness, Subconsciousness, and Soul.
        """
        brain_status = self.brain.get_status()
        cons_status = self.consciousness.get_status()
        subc_status = self.subconsciousness.get_status()
        soul_status = self.soul.get_status()

        # Compute Holistic Cognitive Harmony Index (0 - 100)
        brain_h = brain_status.get("health_score", 100.0)
        cons_h = cons_status.get("meta_critique_vitals", {}).get("average_quality_score", 100.0)
        soul_h = soul_status.get("latest_audit", {}).get("alignment_score", 100.0) if soul_status.get("latest_audit") else 100.0

        harmony_score = round((brain_h * 0.35) + (cons_h * 0.35) + (soul_h * 0.30), 1)

        return {
            "status": "success",
            "cognitive_harmony_index": harmony_score,
            "overall_state": "ENLIGHTENED" if harmony_score >= 90 else ("COHERENT" if harmony_score >= 75 else "DISSONANT"),
            "timestamp": datetime.now().isoformat(),
            "layers": {
                "brain": brain_status,
                "consciousness": cons_status,
                "subconsciousness": subc_status,
                "soul": soul_status,
            },
        }
