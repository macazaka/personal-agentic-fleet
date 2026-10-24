"""
Automated Verification Suite for Personal Agentic Fleet.
Tests the Deterministic Event Bus (A2A) and the FastMCP Server.
"""

import os
import sys

os.environ["FLEET_TEST_MODE"] = "1"

from fleet.core.event_bus import FleetEvent, bus
import fleet.mcp_server as mcp_module


def test_event_bus_a2a():
    print("Testing Deterministic Event Bus (0-Token A2A)...")

    # 1. Add Task via A2A
    event_add = FleetEvent(
        sender="TestAgent",
        target="agenda",
        action="ADD_TASK",
        payload={"title": "Automated Test Task", "priority": "P1"}
    )
    res_add = bus.dispatch(event_add)
    assert res_add["status"] == "success", f"Add task failed: {res_add}"
    task_id = res_add["data"]["task_id"]
    print(f"  [PASS] A2A ADD_TASK -> Task ID #{task_id}")

    # 2. List Tasks via A2A
    event_list = FleetEvent(sender="TestAgent", target="agenda", action="LIST_TASKS")
    res_list = bus.dispatch(event_list)
    assert res_list["status"] == "success", f"List tasks failed: {res_list}"
    tasks = res_list["data"]["tasks"]
    assert any(t["id"] == task_id for t in tasks), "Newly created task not in task list"
    print(f"  [PASS] A2A LIST_TASKS -> Total tasks: {len(tasks)}")

    # 3. Complete Task via A2A
    event_comp = FleetEvent(
        sender="TestAgent",
        target="agenda",
        action="COMPLETE_TASK",
        payload={"task_id": task_id}
    )
    res_comp = bus.dispatch(event_comp)
    assert res_comp["status"] == "success", f"Complete task failed: {res_comp}"
    print(f"  [PASS] A2A COMPLETE_TASK -> Completed #{task_id}")

    # 4. Get Briefing via A2A
    event_briefing = FleetEvent(sender="TestAgent", target="agenda", action="GET_BRIEFING")
    res_briefing = bus.dispatch(event_briefing)
    assert res_briefing["status"] == "success", f"Briefing failed: {res_briefing}"
    assert "headline" in res_briefing["data"]
    print(f"  [PASS] A2A GET_BRIEFING -> Headline: '{res_briefing['data']['headline']}'")


def test_fastmcp_tools():
    print("\nTesting FastMCP Tools...")
    # Direct tool invocation
    briefing = mcp_module.fleet_get_daily_briefing()
    assert isinstance(briefing, str) and len(briefing) > 0
    print("  [PASS] FastMCP fleet_get_daily_briefing() returned markdown")

    add_res = mcp_module.fleet_add_task("MCP Direct Task", priority="P2")
    assert "Successfully added task" in add_res
    print(f"  [PASS] FastMCP fleet_add_task() -> {add_res}")

    list_res = mcp_module.fleet_list_tasks(limit=100)
    assert "MCP Direct Task" in list_res

    print("  [PASS] FastMCP fleet_list_tasks() confirmed task in list")

    routines_res = mcp_module.fleet_list_routines()
    assert "Daily Routines" in routines_res
    print("  [PASS] FastMCP fleet_list_routines() confirmed routines")


if __name__ == "__main__":
    test_event_bus_a2a()
    test_fastmcp_tools()
    print("\nALL DETERMINISTIC A2A & FASTMCP TESTS PASSED SUCCESSFULLY! (0 Tokens Spent)")

