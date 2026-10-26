"""
Comprehensive test suite for the Cognitive Fleet Mind architecture:
Brain, Consciousness, Subconsciousness, and Soul.
Verifies self-healing, self-improving, and self-critiquing deterministic loops.
"""

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from fleet.core.database import FleetDatabase
from fleet.core.event_bus import FleetEvent, bus, event_bus
from fleet.core.mind import fleet_mind
from fleet.core.mind.brain import EpistemicMemoryStats, PhysicalBrain, WorkingMemorySnapshot
from fleet.core.mind.consciousness import ConsciousExecutive, ConsciousnessState, CritiqueResult, SelfCritiqueEngine
from fleet.core.mind.gestalt import CognitiveFleetMind
from fleet.core.mind.soul import CoreValue, FleetSoul, SoulAuditResult
from fleet.core.mind.subconsciousness import DreamInsight, SubconsciousMind
from fleet.tools.fleet_mind import format_status_text


class TestCognitiveMind(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_mind_db.sqlite"
        self.db = FleetDatabase(db_path=self.db_path)
        self.mind = CognitiveFleetMind(db=self.db)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # --- 1. Brain Tests ---

    def test_brain_synapse_firing_and_telemetry(self):
        brain = PhysicalBrain(db=self.db)
        initial_synapses = brain.get_status()["synapses_fired"]
        brain.record_synapse_firing()
        brain.record_synapse_firing()
        status = brain.get_status()
        self.assertEqual(status["synapses_fired"], initial_synapses + 2)
        self.assertIn("working_memory", status)
        self.assertIn("epistemic_memory", status)
        self.assertGreaterEqual(status["health_score"], 0.0)

    def test_brain_autonomic_reflex_arc(self):
        brain = PhysicalBrain(db=self.db)
        reflex_result = brain.trigger_autonomic_reflex()
        self.assertEqual(reflex_result["status"], "HEALTHY")
        self.assertIn("health_score", reflex_result)
        self.assertIsInstance(reflex_result["anomalies_detected"], list)
        self.assertIsInstance(reflex_result["auto_repairs_applied"], list)

    # --- 2. Consciousness & Self-Critique Tests ---

    def test_consciousness_attention_state(self):
        cons = ConsciousExecutive(db=self.db)
        cons.set_attention(agent="PCOptimizer", goal="Clean system temp files", state=ConsciousnessState.FOCUSED)
        status = cons.get_status()
        self.assertEqual(status["executive_attention"]["active_agent"], "PCOptimizer")
        self.assertEqual(status["executive_attention"]["current_goal"], "Clean system temp files")
        self.assertEqual(status["executive_attention"]["state"], "FOCUSED")

    def test_self_critique_engine_evaluation(self):
        engine = SelfCritiqueEngine(db=self.db)
        # 1. Clean successful action evaluation
        good_critique = engine.evaluate(
            agent="HealthManager",
            action="evaluate_system",
            input_payload={"check_disk": True},
            output_result={"status": "success", "health_score": 98.5, "details": "Normal operation"},
        )
        self.assertTrue(good_critique.passed)
        self.assertGreaterEqual(good_critique.score, 85.0)
        self.assertTrue(len(good_critique.strengths) > 0)
        self.assertEqual(len(good_critique.deficiencies), 0)

        # 2. Deficient / failing action evaluation
        bad_critique = engine.evaluate(
            agent="NetworkAgent",
            action="ping_host",
            input_payload={"host": "invalid_domain"},
            output_result={"status": "error", "error": "Connection timeout after 30s"},
        )
        self.assertFalse(bad_critique.passed)
        self.assertLess(bad_critique.score, 70.0)
        self.assertTrue(len(bad_critique.deficiencies) > 0)
        self.assertTrue(len(bad_critique.corrective_action) > 0)

    # --- 3. Subconsciousness & Dream Cycle Tests ---

    def test_subconscious_dream_cycle_memory_consolidation(self):
        subc = SubconsciousMind(db=self.db)
        # Populate episodic memory with activities
        for i in range(10):
            self.db.log_activity("PCOptimizer", "clean_temp", f"Reclaimed {i*10} MB temporary disk space")
        for i in range(5):
            self.db.log_activity("HealthManager", "evaluate_system", f"Health status check {i}")
        self.db.add_task("Routine System Sweep", priority="P1", assigned_agent="PCOptimizer")

        dream_result = subc.run_dream_cycle(max_activities_to_synthesize=50)
        self.assertIn("cycle_id", dream_result)
        self.assertGreaterEqual(dream_result["events_consolidated"], 15)
        self.assertGreaterEqual(dream_result["insights_synthesized_count"], 1)
        self.assertTrue(len(dream_result["insights"]) > 0)

        # Verify insights persisted to database
        db_insights = self.db.list_dream_insights(limit=10)
        self.assertGreaterEqual(len(db_insights), 1)

    # --- 4. Soul & Teleological Compass Tests ---

    def test_soul_core_tenets_and_alignment_audit(self):
        soul = FleetSoul(db=self.db)
        audit = soul.audit_alignment()
        self.assertIsInstance(audit, SoulAuditResult)
        self.assertGreaterEqual(audit.alignment_score, 90.0)
        self.assertIn(audit.status, ["PURE", "FAITHFUL"])
        self.assertEqual(len(audit.violations), 0)
        self.assertGreater(len(audit.tenets_evaluated), 0)

        # Verify audit logged to database
        audits_in_db = self.db.list_soul_audits(limit=5)
        self.assertGreaterEqual(len(audits_in_db), 1)

    def test_soul_evolutionary_self_improvement(self):
        soul = FleetSoul(db=self.db)
        gen_before = soul.get_status()["generation"]
        res = soul.evolve_and_improve()
        gen_after = res["generation"]
        self.assertEqual(gen_after, gen_before + 1)
        self.assertTrue(len(res["evolutionary_directives_applied"]) > 0)

    # --- 5. Gestalt Cognitive Mind Tests ---

    def test_gestalt_holistic_state_and_harmony_score(self):
        state = self.mind.get_holistic_state()
        self.assertEqual(state["status"], "success")
        self.assertGreaterEqual(state["cognitive_harmony_index"], 80.0)
        self.assertIn(state["overall_state"], ["ENLIGHTENED", "COHERENT"])
        self.assertIn("brain", state["layers"])
        self.assertIn("consciousness", state["layers"])
        self.assertIn("subconsciousness", state["layers"])
        self.assertIn("soul", state["layers"])

    def test_gestalt_convenience_methods(self):
        # Critique
        crit = self.mind.critique("TestAgent", "test_action", {}, {"status": "success", "result": "ok"})
        self.assertIsInstance(crit, CritiqueResult)
        self.assertTrue(crit.passed)

        # Dream
        dream = self.mind.dream(max_activities=50)
        self.assertIn("cycle_id", dream)

        # Soul audit
        audit = self.mind.audit_soul()
        self.assertIsInstance(audit, SoulAuditResult)

        # Evolve
        evolve = self.mind.self_improve()
        self.assertGreaterEqual(evolve["generation"], 1)

        # Heal
        heal = self.mind.heal()
        self.assertIn(heal["status"], ["HEALTHY", "RECOVERING"])

    # --- 6. Event Bus Synapses & Critique Integration ---

    def test_event_bus_synaptic_and_critique_hook(self):
        fleet_mind.set_db(self.db)
        initial_synapses = fleet_mind.brain.synapses_fired

        # Dispatch FleetEvent -> records synapse firing and executes mind handler
        evt = FleetEvent(sender="test_suite", target="mind", action="STATUS", payload={})
        res = event_bus.dispatch(evt)
        self.assertEqual(res.get("status"), "success")
        self.assertGreaterEqual(fleet_mind.brain.synapses_fired, initial_synapses + 1)

    # --- 7. CLI Formatter Test ---

    def test_cli_format_status_text(self):
        state = self.mind.get_holistic_state()
        formatted = format_status_text(state)
        self.assertIn("PERSONAL AGENTIC FLEET — COGNITIVE MIND STATUS", formatted)
        self.assertIn("1. BRAIN", formatted)
        self.assertIn("2. CONSCIOUSNESS", formatted)
        self.assertIn("3. SUBCONSCIOUSNESS", formatted)
        self.assertIn("4. SOUL", formatted)

    # --- 8. REST API Endpoints Test ---

    def test_mind_rest_api_endpoints(self):
        from unittest.mock import MagicMock
        import urllib.parse
        from fleet.api.router import router
        import fleet.server as srv

        srv.db = self.db
        handler = MagicMock()
        last_json = {}

        def mock_send_json(data, status=200):
            nonlocal last_json
            last_json = data

        handler._send_json = mock_send_json

        # 1. GET /api/mind/status
        handled = router.dispatch_get(handler, "/api/mind/status", urllib.parse.urlparse("/api/mind/status"))
        self.assertTrue(handled)
        self.assertEqual(last_json.get("status"), "success")

        # 2. GET /api/mind/insights
        handled = router.dispatch_get(handler, "/api/mind/insights", urllib.parse.urlparse("/api/mind/insights?limit=5"))
        self.assertTrue(handled)
        self.assertIn("insights", last_json)

        # 3. GET /api/mind/critiques
        handled = router.dispatch_get(handler, "/api/mind/critiques", urllib.parse.urlparse("/api/mind/critiques?limit=5"))
        self.assertTrue(handled)
        self.assertIn("critiques", last_json)

        # 4. GET /api/mind/soul/audits
        handled = router.dispatch_get(handler, "/api/mind/soul/audits", urllib.parse.urlparse("/api/mind/soul/audits?limit=5"))
        self.assertTrue(handled)
        self.assertIn("audits", last_json)

        # 5. POST /api/mind/critique
        handled = router.dispatch_post(handler, "/api/mind/critique", {"agent": "Test", "action": "test", "result": {"status": "ok"}})
        self.assertTrue(handled)
        self.assertEqual(last_json.get("status"), "success")

        # 6. POST /api/mind/dream
        handled = router.dispatch_post(handler, "/api/mind/dream", {"max_activities": 10})
        self.assertTrue(handled)
        self.assertEqual(last_json.get("status"), "success")

        # 7. POST /api/mind/soul/audit
        handled = router.dispatch_post(handler, "/api/mind/soul/audit", {})
        self.assertTrue(handled)
        self.assertEqual(last_json.get("status"), "success")

        # 8. POST /api/mind/self_improve
        handled = router.dispatch_post(handler, "/api/mind/self_improve", {})
        self.assertTrue(handled)
        self.assertEqual(last_json.get("status"), "ASCENDING")

        # 9. POST /api/mind/heal
        handled = router.dispatch_post(handler, "/api/mind/heal", {})
        self.assertTrue(handled)
        self.assertIn(last_json.get("status"), ["HEALTHY", "RECOVERING"])


if __name__ == "__main__":
    unittest.main()
