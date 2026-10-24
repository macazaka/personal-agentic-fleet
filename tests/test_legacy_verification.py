"""Unit tests executing legacy test modules fleet.test_fleet and fleet.test_gmail_classifier."""
from unittest.mock import patch

import fleet.test_fleet as tf_mod
import fleet.test_gmail_classifier as tgc_mod


def test_legacy_test_fleet_module():
    # Execute test_event_bus_a2a and test_fastmcp_tools
    tf_mod.test_event_bus_a2a()
    tf_mod.test_fastmcp_tools()


def test_legacy_test_gmail_classifier_module():
    # Execute test_lookback_query, test_tier0_classification_accuracy, test_event_bus_and_mcp
    tgc_mod.test_lookback_query()
    tgc_mod.test_tier0_classification_accuracy()
    with patch("fleet.integrations.gmail_client.gmail_manager.is_connected", False):
        with patch("fleet.integrations.gmail_client.gmail_manager.service", None):
            tgc_mod.test_event_bus_and_mcp()



