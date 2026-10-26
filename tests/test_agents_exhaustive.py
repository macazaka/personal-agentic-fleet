"""
Exhaustive Unit Tests for all Fleet Built-In Agents:
- HealthAgent
- OverviewAgent
- OptimizerAgent
- BacklogAgent
- AntigravityAgent
- GmailAgent
- PRReviewAgent
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.core.database import FleetDatabase
from fleet.agents.health.agent import HealthAgent
from fleet.agents.overview.agent import OverviewAgent
from fleet.agents.optimizer.agent import OptimizerAgent
from fleet.agents.backlog.agent import BacklogAgent
from fleet.agents.antigravity.agent import AntigravityAgent
from fleet.agents.gmail.agent import GmailAgent
from fleet.agents.pr_review.agent import PRReviewAgent

AGENTS_DIR = Path(__file__).parent.parent / "fleet" / "agents"


@pytest.fixture
def agent_env(tmp_path):
    db = FleetDatabase(tmp_path / "test_agents.db")
    bus = MagicMock()
    bus.dispatch.return_value = {"status": "success", "data": {"counts": {"Meetings": 1, "Respond": 2}}}
    return {"db": db, "bus": bus, "tmp_path": tmp_path}


def test_health_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "health"
    agent = HealthAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "health"
    assert agent.name == "Health & Wellness"
    assert agent.icon == "🌿"
    assert agent.order == 10
    assert agent.is_default is True

    # Routes
    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    # Tasks
    tasks = [
        "smoothie_reminder",
        "breakfast_meds",
        "lunch_meds",
        "afternoon_snack",
        "dinner_meds",
        "sleep_recovery",
        "routine_check",
        "unknown_task",
    ]
    for t in tasks:
        res = agent.execute_task(t)
        assert res["status"] in ("success", "SUCCESS")


def test_overview_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "overview"
    agent = OverviewAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "overview"
    assert agent.name == "Overview & Tasks"
    assert agent.icon == "⚡"
    assert agent.order == 20
    assert agent.is_default is False

    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    # Morning & evening briefing tasks
    res_m = agent.execute_task("morning_briefing")
    assert res_m["status"] == "success"

    res_e = agent.execute_task("evening_review")
    assert res_e["status"] == "success"

    res_u = agent.execute_task("other_task")
    assert res_u["status"] == "SUCCESS"


def test_optimizer_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "optimizer"
    agent = OptimizerAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "optimizer"
    assert agent.name == "PC Optimizer"
    assert agent.icon == "🚀"
    assert agent.order == 30
    assert agent.is_default is False

    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    res = agent.execute_task("optimize_pulse")
    assert res["status"] == "success"
    assert "RAM Optimized" in res["message"]


def test_backlog_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "backlog"
    agent = BacklogAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "backlog"
    assert agent.name == "Feature Backlog"
    assert agent.icon == "📋"
    assert agent.order == 50

    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    res = agent.execute_task("hygiene_check")
    assert res["status"] == "success"


def test_antigravity_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "antigravity"
    agent = AntigravityAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "antigravity"
    assert agent.name == "Antigravity Live"
    assert agent.icon == "🤖"
    assert agent.order == 40

    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    with patch("fleet.core.antigravity_mirror.process_next_in_queue"), \
         patch("fleet.core.antigravity_mirror.get_token_health", return_value={"percent_used": 15, "status": "Optimal"}):
        res = agent.execute_task("queue_pulse")
        assert res["status"] == "success"


def test_gmail_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "gmail"
    agent = GmailAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "gmail"
    assert agent.name == "Email Intelligence"
    assert agent.icon == "📧"
    assert agent.order == 60

    router = ApiRouter()
    agent.register_routes(router)
    assert len(router.get_routes) > 0

    res = agent.execute_task("triage")
    assert res["status"] == "success"


def test_pr_review_agent_lifecycle(agent_env):
    agent_dir = AGENTS_DIR / "pr_review"
    agent = PRReviewAgent(agent_dir=agent_dir, db=agent_env["db"], event_bus=agent_env["bus"])
    assert agent.id == "pr_review"
    assert agent.icon == "🛡️"
    assert agent.order == 70

    router = ApiRouter()
    agent.register_routes(router)

    handler = MagicMock()
    with patch.object(agent, "audit_pull_requests", return_value=[]), \
         patch.object(agent, "check_ci_status", return_value={"status": "PASS"}):
        fn = router.get_routes.get("/api/pr_review/status")
        assert fn is not None
        fn(handler, urllib.parse.urlparse("/api/pr_review/status"))
        assert handler._send_json.called

    # Tasks
    with patch.object(agent, "audit_pull_requests", return_value=[{"number": 1, "title": "PR 1"}]), \
         patch.object(agent, "check_ci_status", return_value={"status": "PASS"}):
        prs = agent.execute_task("poll_prs")
        assert isinstance(prs, list)
        assert len(prs) == 1

        ci = agent.execute_task("ci_status")
        assert ci["status"] == "PASS"

        unknown = agent.execute_task("something_else")
        assert unknown["status"] == "UNKNOWN_TASK"

