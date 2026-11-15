"""
Tri-Device Ecosystem & Hardware Connections Agent (`tri_device`).

Manages all external hardware, wearable, mobile, and protocol connections in one dedicated place
(separated from the Health & Wellness Agent):
  1. ⌚ Apple Watch (watchOS) via Mandatory iPhone Companion Relay:
     - Apple Watch NEVER pairs directly to a Windows laptop (Apple hardware/OS restriction:
       Apple Watch only pairs with a compatible iPhone via WatchConnectivity & HealthKit).
     - All Apple Watch vitals (HRV SDNN, Resting HR, Sleep Stages, SpO2,Steps, Active Calories,
       Wrist Temperature) sync first to iPhone HealthKit (`HKHealthStore`) and are relayed by
       the iPhone Companion Bridge (`ChandavaneMaCaZaKa`) over encrypted Wi-Fi LAN / Tailscale to Windows.
  2. 📱 iPhone Companion Bridge (`ChandavaneMaCaZaKa`):
     - Windows Bluetooth Registry presence + RFC-1918 Wi-Fi LAN Gateway (`http://192.168.1.35:7890/mobile-pair`)
     - iOS Shortcuts Automation & Apple Health `export.xml` / JSON ingestion
  3. 🌐 Network & Mesh Bridges:
     - Local Wi-Fi LAN Gateway (`0.0.0.0:7890`), Tailscale WireGuard Mesh (`100.x.y.z`), & Root CA TLS
  4. 💳 Mobile Open Payment Bridge:
     - 1-Tap `upi://pay` Deep-Link & QR handoff to iPhone (BHIM, ICICI iMobile, GPay, PhonePe)
  5. 🎙️ Local Audio & Biometric Hardware:
     - Windows Microphone DSP (85–3800 Hz) + 6D Speaker Voiceprint Lock ("Mahadev")
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fleet.core.base_agent import FleetAgent


class TriDeviceConnectionAgent(FleetAgent):
    """Dedicated Tri-Device Ecosystem & External Hardware Connections Agent."""

    def __init__(
        self,
        agent_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
        event_bus=None,
        db=None,
    ):
        base_dir = agent_dir or Path(__file__).resolve().parent
        default_cfg = {
            "enabled": True,
            "category": "Connection Agents",
            "description": (
                "Manages all hardware & external device connections: Apple Watch (via mandatory iPhone "
                "Companion Relay), iPhone Bridge (ChandavaneMaCaZaKa), Wi-Fi LAN & Tailscale Mesh, "
                "1-Tap Mobile UPI Payment Link, and Local Biometric Audio DSP."
            ),
            "permissions": [
                "bluetooth_registry_read",
                "lan_bridge_gateway",
                "iphone_companion_relay",
                "healthkit_webhook_ingest",
                "upi_deep_link",
            ],
        }
        if config:
            default_cfg.update(config)
        super().__init__(agent_dir=base_dir, config=default_cfg, event_bus=event_bus, db=db)

    @property
    def id(self) -> str:
        return "tri_device"

    @property
    def name(self) -> str:
        return "Tri-Device & Connections"

    @property
    def icon(self) -> str:
        return "⌚"

    @property
    def order(self) -> int:
        return 15

    def get_ui_manifest(self) -> Dict[str, Any]:
        manifest = super().get_ui_manifest()
        manifest["category"] = "Connection Agents"
        manifest["description"] = (
            "Tri-Device Ecosystem Hub & Hardware Connection Manager — Apple Watch (via iPhone Companion "
            "Relay), iPhone Bridge (ChandavaneMaCaZaKa), Wi-Fi LAN / Tailscale Gateway, UPI Payment "
            "Deep-Link Bridge, and Audio Biometric Hardware."
        )
        manifest["permissions"] = [
            "iphone_companion_relay",
            "bluetooth_registry_read",
            "wifi_lan_gateway",
            "tailscale_mesh",
            "upi_deep_link",
        ]
        return manifest

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "iphone_companion_name",
                "label": "Paired iPhone Companion Bridge Name",
                "type": "text",
                "default": "ChandavaneMaCaZaKa",
                "description": (
                    "Your iPhone acts as the mandatory relay between Apple Watch (watchOS) and this "
                    "Windows laptop, since Apple Watch only pairs directly with an iPhone."
                ),
            },
            {
                "id": "lan_gateway_port",
                "label": "Wi-Fi LAN & Tailscale Bridge Port",
                "type": "number",
                "default": 7890,
                "description": "Local HTTP/HTTPS listener port for iPhone Shortcuts & Safari Mobile Pair",
            },
            {
                "id": "auto_forward_vitals_to_health",
                "label": "Forward Synced Watch Vitals to Health Agent",
                "type": "boolean",
                "default": True,
                "description": (
                    "When iPhone relays Apple Watch HealthKit vitals to Tri-Device Hub, automatically "
                    "store metrics in local SQLite for the Health & Wellness Agent."
                ),
            },
        ]

    def get_micro_widget(self) -> Dict[str, Any]:
        return {
            "agent_id": self.id,
            "title": self.display_name,
            "icon": self.display_icon,
            "size": "1x1",
            "primary_metric": "Watch ➔ iPhone ➔ PC",
            "secondary_label": "Connection Agents Hub",
            "quick_action": {
                "label": "⌚ Verify & Sync",
                "task": "verify_and_sync",
            },
        }

    def execute_task(self, task_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        if task_name in ("verify_and_sync", "status", "run_check"):
            from fleet.api.mobile_tri_device_api import _scan_windows_bluetooth_and_lan_apple_devices

            hw = _scan_windows_bluetooth_and_lan_apple_devices()
            return {
                "status": "success",
                "agent": self.id,
                "category": "Connection Agents",
                "architecture_rule": (
                    "Apple Watch pairs exclusively with a compatible iPhone (never directly to Windows). "
                    "iPhone acts as the encrypted HealthKit & WatchConnectivity relay bridge to the Windows AFCC Hub."
                ),
                "hardware": hw,
                "timestamp": datetime.now().isoformat(),
            }
        return {
            "status": "success",
            "agent": self.id,
            "task": task_name,
            "timestamp": datetime.now().isoformat(),
        }
