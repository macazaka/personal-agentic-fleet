from fleet.agents.pr_review.agent import PRReviewAgent


def test_pr_review_agent_initialization():
    agent = PRReviewAgent(config={"repository": "macazaka/personal-agentic-fleet", "interval_minutes": 30})
    assert agent.id == "pr_review"
    assert agent.name == "Admin PR Review & CI Quality Gate"
    assert agent.repo == "macazaka/personal-agentic-fleet"
    assert agent.check_interval_minutes == 30


def test_pr_review_agent_audit_pull_requests_mock(monkeypatch):
    agent = PRReviewAgent()
    import urllib.request
    from io import BytesIO

    mock_json = b'[{"number": 42, "title": "Test PR", "user": {"login": "dependabot[bot]"}, "head": {"sha": "abc1234"}, "draft": false, "html_url": "https://github.com/..."}]'

    class MockResp:
        def read(self):
            return mock_json
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: MockResp())
    res = agent.audit_pull_requests()
    assert res["status"] == "SUCCESS"
    assert res["open_count"] == 1
    assert res["prs"][0]["number"] == 42
    assert res["prs"][0]["is_dependabot"] is True


def test_pr_review_agent_check_ci_status_mock(monkeypatch):
    agent = PRReviewAgent()
    import urllib.request

    mock_json = b'{"workflow_runs": [{"id": 101, "name": "Fleet CI", "conclusion": "failure", "head_sha": "abc1234", "html_url": "https://github.com/..."}]}'

    class MockResp:
        def read(self):
            return mock_json
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: MockResp())
    res = agent.check_ci_status()
    assert res["status"] == "FAILING"
    assert len(res["failing_runs"]) == 1

