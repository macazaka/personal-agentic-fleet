"""
Mind Framework — Cognitive Architecture for Personal Agentic Fleet.
Brain, Consciousness, Subconsciousness, and Soul.
"""

from fleet.core.mind.brain import PhysicalBrain, WorkingMemorySnapshot, EpistemicMemoryStats
from fleet.core.mind.consciousness import (
    ConsciousExecutive,
    ConsciousnessState,
    CritiqueResult,
    ExecutiveAttention,
    SelfCritiqueEngine,
)
from fleet.core.mind.subconsciousness import SubconsciousMind, DreamInsight
from fleet.core.mind.soul import FleetSoul, CoreValue, SoulAuditResult
from fleet.core.mind.gestalt import CognitiveFleetMind

# Global Cognitive Fleet Mind Singleton
fleet_mind = CognitiveFleetMind()

__all__ = [
    "fleet_mind",
    "CognitiveFleetMind",
    "PhysicalBrain",
    "WorkingMemorySnapshot",
    "EpistemicMemoryStats",
    "ConsciousExecutive",
    "ConsciousnessState",
    "CritiqueResult",
    "ExecutiveAttention",
    "SelfCritiqueEngine",
    "SubconsciousMind",
    "DreamInsight",
    "FleetSoul",
    "CoreValue",
    "SoulAuditResult",
]
