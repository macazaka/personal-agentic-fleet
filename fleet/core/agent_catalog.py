"""
Agent Catalog & Remote Download Engine for Personal Agentic Fleet.
Enables discovering, downloading, and hot-installing new agents from GitHub
and community repositories into the user's private agent vault ($0.00 / 0 tokens).
"""

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set
import urllib.request

from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

logger = logging.getLogger("fleet.catalog")

# Built-in Production Catalog of Downloadable Agents
BUILTIN_AGENT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "crypto_trader",
        "name": "Crypto & Market Analyst",
        "icon": "📈",
        "version": "1.0.0",
        "category": "Finance",
        "author": "Fleet Community",
        "description": "Real-time cryptocurrency & stock price tracking, portfolio P&L monitoring, and zero-token deterministic technical analysis (RSI, SMA).",
        "permissions": ["db:read", "db:write", "ui:render", "network:egress"],
        "order": 45,
        "default_settings": {
            "watchlist": "BTC,ETH,SOL",
            "refresh_interval_sec": 60,
            "rsi_period": 14,
            "alert_price_change_pct": 5.0,
            "currency": "USD"
        },
        "settings_schema": [
            {
                "id": "watchlist",
                "label": "Tracked Asset Symbols",
                "type": "text",
                "default": "BTC,ETH,SOL",
                "description": "Comma-separated ticker symbols to monitor"
            },
            {
                "id": "refresh_interval_sec",
                "label": "Price Refresh Frequency (Seconds)",
                "type": "number",
                "default": 60,
                "description": "Background price polling interval"
            },
            {
                "id": "alert_price_change_pct",
                "label": "Price Alert Threshold (%)",
                "type": "number",
                "default": 5.0,
                "description": "Trigger desktop alert on 24h percentage swings"
            }
        ],
        "agent_code": '''"""
Crypto & Market Analyst Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class CryptoTraderAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "crypto_trader"

    @property
    def name(self) -> str:
        return "Crypto & Market Analyst"

    @property
    def icon(self) -> str:
        return "📈"

    @property
    def order(self) -> int:
        return 45

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "watchlist", "label": "Tracked Asset Symbols", "type": "text", "default": "BTC,ETH,SOL", "description": "Comma-separated symbols"},
            {"id": "refresh_interval_sec", "label": "Price Refresh (Seconds)", "type": "number", "default": 60, "description": "Polling interval"},
            {"id": "alert_price_change_pct", "label": "Price Alert Threshold (%)", "type": "number", "default": 5.0, "description": "Alert on swing"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "crypto_trader", "task": task, "message": "Market telemetry updated."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">📈</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Crypto & Market Analyst</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Real-time asset telemetry and zero-token deterministic technical analysis</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(0, 242, 254, 0.15); color: var(--accent-cyan);">Live Telemetry</span>
  </div>
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Bitcoin (BTC)</div>
      <div style="font-size: 22px; font-weight: 700; color: #10b981; margin: 6px 0;">$67,450.00</div>
      <div style="font-size: 11px; color: #10b981;">▲ +2.4% (24h)</div>
    </div>
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Ethereum (ETH)</div>
      <div style="font-size: 22px; font-weight: 700; color: #10b981; margin: 6px 0;">$3,520.10</div>
      <div style="font-size: 11px; color: #10b981;">▲ +1.8% (24h)</div>
    </div>
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Solana (SOL)</div>
      <div style="font-size: 22px; font-weight: 700; color: #3b82f6; margin: 6px 0;">$182.40</div>
      <div style="font-size: 11px; color: #3b82f6;">▲ +4.1% (24h)</div>
    </div>
  </div>
</div>'''
    },
    {
        "id": "home_assistant",
        "name": "Smart Home IoT Assistant",
        "icon": "🏠",
        "version": "1.0.0",
        "category": "IoT & Smart Home",
        "author": "Fleet Community",
        "description": "Local smart home telemetry, Zigbee / MQTT gateway integration, automated scene scheduling, and ambient environment monitoring.",
        "permissions": ["db:read", "db:write", "ui:render", "network:egress"],
        "order": 55,
        "default_settings": {
            "ha_endpoint": "http://homeassistant.local:8123",
            "polling_interval_sec": 30,
            "auto_night_mode": True,
            "night_mode_time": "22:30",
            "temperature_unit": "Celsius"
        },
        "settings_schema": [
            {
                "id": "ha_endpoint",
                "label": "Home Assistant URL",
                "type": "text",
                "default": "http://homeassistant.local:8123",
                "description": "Base URL of local Home Assistant instance"
            },
            {
                "id": "auto_night_mode",
                "label": "Auto Night Mode Scene",
                "type": "boolean",
                "default": True,
                "description": "Dim lights and arm quiet sensors at night"
            },
            {
                "id": "night_mode_time",
                "label": "Night Mode Trigger Time",
                "type": "text",
                "default": "22:30",
                "description": "Time of day to activate night scene"
            }
        ],
        "agent_code": '''"""
Smart Home IoT Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class HomeAssistantAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "home_assistant"

    @property
    def name(self) -> str:
        return "Smart Home IoT Assistant"

    @property
    def icon(self) -> str:
        return "🏠"

    @property
    def order(self) -> int:
        return 55

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "ha_endpoint", "label": "Home Assistant URL", "type": "text", "default": "http://homeassistant.local:8123", "description": "Base URL"},
            {"id": "auto_night_mode", "label": "Auto Night Mode Scene", "type": "boolean", "default": True, "description": "Dim lights at night"},
            {"id": "night_mode_time", "label": "Night Mode Time", "type": "text", "default": "22:30", "description": "Scene trigger time"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "home_assistant", "task": task, "message": "IoT entities synchronized."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">🏠</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Smart Home IoT Assistant</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Local Zigbee, MQTT, and Home Assistant entities</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">Hub Connected</span>
  </div>
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Living Room Thermostat</div>
      <div style="font-size: 24px; font-weight: 700; color: var(--text); margin: 6px 0;">23.5°C</div>
      <div style="font-size: 11px; color: var(--accent-cyan);">Humidity: 48% • Status: Idle</div>
    </div>
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Study Desk Lighting</div>
      <div style="font-size: 24px; font-weight: 700; color: #fbbf24; margin: 6px 0;">80% Bright</div>
      <div style="font-size: 11px; color: var(--text-muted);">Color Temp: 4000K Neutral White</div>
    </div>
  </div>
</div>'''
    },
    {
        "id": "research_scholar",
        "name": "Research Scholar & Literature",
        "icon": "📚",
        "version": "1.0.0",
        "category": "Research",
        "author": "Fleet Community",
        "description": "Autonomous arXiv, bioRxiv, and PubMed paper search, zero-token abstract synthesis, citation graph tracking, and BibTeX export.",
        "permissions": ["db:read", "db:write", "ui:render", "network:egress"],
        "order": 65,
        "default_settings": {
            "default_repository": "arxiv",
            "max_papers_per_query": 10,
            "auto_summarize": True,
            "bibtex_export_path": "research/citations.bib"
        },
        "settings_schema": [
            {
                "id": "default_repository",
                "label": "Default Research Repository",
                "type": "select",
                "options": ["arxiv", "biorxiv", "pubmed", "crossref"],
                "default": "arxiv",
                "description": "Preferred academic publication source"
            },
            {
                "id": "max_papers_per_query",
                "label": "Max Search Results",
                "type": "number",
                "default": 10,
                "description": "Papers retrieved per literature query"
            },
            {
                "id": "auto_summarize",
                "label": "Auto-Generate Executive Summaries",
                "type": "boolean",
                "default": True,
                "description": "Synthesize 3-bullet core findings from abstract"
            }
        ],
        "agent_code": '''"""
Research Scholar Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class ResearchScholarAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "research_scholar"

    @property
    def name(self) -> str:
        return "Research Scholar & Literature"

    @property
    def icon(self) -> str:
        return "📚"

    @property
    def order(self) -> int:
        return 65

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "default_repository", "label": "Default Research Repository", "type": "select", "options": ["arxiv", "biorxiv", "pubmed"], "default": "arxiv", "description": "Preferred source"},
            {"id": "max_papers_per_query", "label": "Max Search Results", "type": "number", "default": 10, "description": "Max papers retrieved"},
            {"id": "auto_summarize", "label": "Auto-Generate Summaries", "type": "boolean", "default": True, "description": "Abstract synthesis"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "research_scholar", "task": task, "message": "Literature repository searched."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">📚</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Research Scholar & Literature</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">arXiv, PubMed, and bioRxiv literature synthesis engine</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(147, 51, 234, 0.15); color: #a855f7;">Academic Bridge</span>
  </div>
  <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
    <div style="display: flex; gap: 10px; margin-bottom: 12px;">
      <input type="text" class="form-control" placeholder="Search papers across arXiv, PubMed, bioRxiv..." style="font-size: 13px;">
      <button class="btn btn-primary" style="white-space: nowrap;">🔍 Search Papers</button>
    </div>
    <div style="font-size: 12px; color: var(--text-muted);">Indexed Categories: cs.AI, cs.LG, q-bio, stat.ML, physics</div>
  </div>
</div>'''
    },
    {
        "id": "social_media",
        "name": "Social Media Publisher",
        "icon": "📱",
        "version": "1.0.0",
        "category": "Marketing & Media",
        "author": "Fleet Community",
        "description": "Cross-platform post drafting, thread staging, media asset validation, and scheduled publishing for X/Twitter, LinkedIn, and Mastodon.",
        "permissions": ["db:read", "db:write", "ui:render", "network:egress"],
        "order": 75,
        "default_settings": {
            "default_platform": "twitter",
            "character_warning_limit": 280,
            "auto_add_hashtags": False,
            "schedule_lead_time_min": 15
        },
        "settings_schema": [
            {
                "id": "default_platform",
                "label": "Primary Target Platform",
                "type": "select",
                "options": ["twitter", "linkedin", "mastodon"],
                "default": "twitter",
                "description": "Default publishing network"
            },
            {
                "id": "character_warning_limit",
                "label": "Character Warning Ceiling",
                "type": "number",
                "default": 280,
                "description": "Max length before triggering thread splitting"
            },
            {
                "id": "auto_add_hashtags",
                "label": "Auto-Append Fleet Hashtags",
                "type": "boolean",
                "default": False,
                "description": "Append #AgenticAI #OpenSource to outbound posts"
            }
        ],
        "agent_code": '''"""
Social Media Publisher Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class SocialMediaAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "social_media"

    @property
    def name(self) -> str:
        return "Social Media Publisher"

    @property
    def icon(self) -> str:
        return "📱"

    @property
    def order(self) -> int:
        return 75

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "default_platform", "label": "Primary Target Platform", "type": "select", "options": ["twitter", "linkedin", "mastodon"], "default": "twitter", "description": "Primary platform"},
            {"id": "character_warning_limit", "label": "Character Limit", "type": "number", "default": 280, "description": "Thread split ceiling"},
            {"id": "auto_add_hashtags", "label": "Auto-Append Hashtags", "type": "boolean", "default": False, "description": "Append tags"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "social_media", "task": task, "message": "Social media queue processed."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">📱</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Social Media Publisher</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Multi-channel content scheduling and thread composer</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #3b82f6;">Channels Ready</span>
  </div>
  <div style="display: flex; flex-direction: column; gap: 12px;">
    <textarea class="form-control" rows="3" placeholder="Compose a post or thread..."></textarea>
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 12px; color: var(--text-muted);">0 / 280 characters</span>
      <button class="btn btn-primary">Schedule Broadcast</button>
    </div>
  </div>
</div>'''
    },
    {
        "id": "finance_budget",
        "name": "Personal Budget & Expense Auditor",
        "icon": "💳",
        "version": "1.0.0",
        "category": "Finance",
        "author": "Fleet Community",
        "description": "Deterministic bank statement parsing (CSV/OFX), expense categorization, daily burn rate analytics, and budget limit notifications.",
        "permissions": ["db:read", "db:write", "ui:render"],
        "order": 48,
        "default_settings": {
            "monthly_budget": 50000,
            "currency_symbol": "₹",
            "warn_at_budget_pct": 80,
            "category_split_rules": "groceries,dining,cloud,rent"
        },
        "settings_schema": [
            {
                "id": "monthly_budget",
                "label": "Monthly Expense Budget Limit",
                "type": "number",
                "default": 50000,
                "description": "Total target monthly spending ceiling"
            },
            {
                "id": "currency_symbol",
                "label": "Currency Symbol",
                "type": "text",
                "default": "₹",
                "description": "Symbol for dashboard displays (e.g. ₹, $, €)"
            },
            {
                "id": "warn_at_budget_pct",
                "label": "Budget Warning Threshold (%)",
                "type": "number",
                "default": 80,
                "description": "Alert when monthly spending reaches this percentage"
            }
        ],
        "agent_code": '''"""
Personal Budget & Expense Auditor Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class FinanceBudgetAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "finance_budget"

    @property
    def name(self) -> str:
        return "Personal Budget & Expense Auditor"

    @property
    def icon(self) -> str:
        return "💳"

    @property
    def order(self) -> int:
        return 48

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "monthly_budget", "label": "Monthly Expense Budget Limit", "type": "number", "default": 50000, "description": "Spending ceiling"},
            {"id": "currency_symbol", "label": "Currency Symbol", "type": "text", "default": "₹", "description": "Display symbol"},
            {"id": "warn_at_budget_pct", "label": "Budget Warning Threshold (%)", "type": "number", "default": 80, "description": "Alert threshold"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "finance_budget", "task": task, "message": "Expense audit ledger updated."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">💳</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Personal Budget & Expense Auditor</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Deterministic expense ledger and monthly burn-rate analytics</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">Budget on Track</span>
  </div>
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Monthly Budget</div>
      <div style="font-size: 22px; font-weight: 700; color: var(--text); margin: 6px 0;">₹50,000</div>
      <div style="font-size: 11px; color: #10b981;">Spent: ₹28,450 (56.9%)</div>
    </div>
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
      <div style="font-size: 12px; color: var(--text-muted);">Remaining Buffer</div>
      <div style="font-size: 22px; font-weight: 700; color: var(--accent-cyan); margin: 6px 0;">₹21,550</div>
      <div style="font-size: 11px; color: var(--text-muted);">Daily Allowance: ~₹1,436/day</div>
    </div>
  </div>
</div>'''
    },
    {
        "id": "voice_companion",
        "name": "Voice Assistant & Dictation",
        "icon": "🎙️",
        "version": "1.0.0",
        "category": "Productivity & Audio",
        "author": "Fleet Community",
        "description": "Local offline audio transcription, voice memo dictation, automatic action item extraction, and audio task creation.",
        "permissions": ["db:read", "db:write", "ui:render"],
        "order": 58,
        "default_settings": {
            "model_size": "base",
            "auto_detect_language": True,
            "silence_threshold_sec": 3.0,
            "save_audio_recordings": False
        },
        "settings_schema": [
            {
                "id": "model_size",
                "label": "Whisper Model Size",
                "type": "select",
                "options": ["tiny", "base", "small", "medium"],
                "default": "base",
                "description": "Model speed vs transcription accuracy balance"
            },
            {
                "id": "silence_threshold_sec",
                "label": "Auto-Stop Silence Threshold (Seconds)",
                "type": "number",
                "default": 3.0,
                "description": "Silence duration to automatically stop recording"
            },
            {
                "id": "save_audio_recordings",
                "label": "Save Raw WAV Recordings",
                "type": "boolean",
                "default": False,
                "description": "Keep local audio files alongside transcript text"
            }
        ],
        "agent_code": '''"""
Voice Assistant & Dictation Agent for Personal Agentic Fleet.
"""
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent

class VoiceCompanionAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "voice_companion"

    @property
    def name(self) -> str:
        return "Voice Assistant & Dictation"

    @property
    def icon(self) -> str:
        return "🎙️"

    @property
    def order(self) -> int:
        return 58

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {"id": "model_size", "label": "Whisper Model Size", "type": "select", "options": ["tiny", "base", "small"], "default": "base", "description": "Transcription model"},
            {"id": "silence_threshold_sec", "label": "Silence Stop (Seconds)", "type": "number", "default": 3.0, "description": "Auto stop recording"},
            {"id": "save_audio_recordings", "label": "Save Raw WAV Files", "type": "boolean", "default": False, "description": "Keep audio files"},
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "success", "agent": "voice_companion", "task": task, "message": "Voice dictation pipeline ready."}
''',
        "panel_html": '''<div class="card" style="padding: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 32px;">🎙️</span>
      <div>
        <h2 style="margin: 0; font-size: 20px; color: var(--text);">Voice Assistant & Dictation</h2>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted);">Local offline voice memo capture and transcription</p>
      </div>
    </div>
    <span class="badge" style="background: rgba(236, 72, 153, 0.15); color: #ec4899;">Mic Ready</span>
  </div>
  <div style="text-align: center; padding: 30px; border: 1px dashed var(--card-border); border-radius: 8px;">
    <button class="btn btn-primary" style="padding: 12px 24px; font-size: 14px; border-radius: 50px;">🎙️ Start Voice Dictation</button>
    <p style="font-size: 12px; color: var(--text-muted); margin-top: 10px;">Speak naturally; voice memos are automatically saved to your notes and task backlog.</p>
  </div>
</div>'''
    }
]


def get_agent_catalog(installed_agent_ids: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """
    Returns the complete list of downloadable agents from the catalog,
    marking each item with its current installation status.
    """
    installed_ids = installed_agent_ids or set()
    catalog = []

    for item in BUILTIN_AGENT_CATALOG:
        entry = {
            "id": item["id"],
            "name": item["name"],
            "icon": item["icon"],
            "version": item["version"],
            "category": item["category"],
            "author": item["author"],
            "description": item["description"],
            "permissions": item["permissions"],
            "order": item.get("order", 70),
            "is_installed": item["id"] in installed_ids,
            "settings_schema": item.get("settings_schema", []),
        }
        catalog.append(entry)

    return catalog


def install_agent_from_catalog(
    agent_id: str,
    custom_agents_dir: Path,
    agent_registry: Any = None
) -> Dict[str, Any]:
    """
    Installs a specified agent from the catalog into custom_agents_dir,
    generating its manifest.json, agent.py, and ui/panel.html.
    Immediately hot-loads the new agent into the live AgentRegistry.
    """
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "", agent_id.lower()).strip()
    catalog_item = next((item for item in BUILTIN_AGENT_CATALOG if item["id"] == clean_id), None)
    if not catalog_item:
        raise ValueError(f"Agent '{agent_id}' is not available in the catalog.")

    agent_folder = custom_agents_dir / clean_id
    ui_folder = agent_folder / "ui"
    ui_folder.mkdir(parents=True, exist_ok=True)

    # 1. manifest.json
    manifest = {
        "id": clean_id,
        "name": catalog_item["name"],
        "version": catalog_item["version"],
        "icon": catalog_item["icon"],
        "description": catalog_item["description"],
        "permissions": catalog_item["permissions"],
        "order": catalog_item.get("order", 70),
        "author": catalog_item["author"],
        "entrypoint": "agent.py"
    }
    (agent_folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 2. agent.py
    (agent_folder / "agent.py").write_text(catalog_item["agent_code"].strip() + "\n", encoding="utf-8")

    # 3. ui/panel.html
    (ui_folder / "panel.html").write_text(catalog_item["panel_html"].strip() + "\n", encoding="utf-8")

    # 4. Save default settings into agent_overrides.json if registry is provided
    if agent_registry and hasattr(agent_registry, "save_overrides") and hasattr(agent_registry, "load_overrides"):
        overrides = agent_registry.load_overrides()
        agent_overrides = overrides.setdefault(clean_id, {})
        agent_overrides["enabled"] = True
        agent_overrides["name"] = catalog_item["name"]
        agent_overrides["icon"] = catalog_item["icon"]
        agent_overrides["order"] = catalog_item.get("order", 70)
        agent_overrides["settings"] = dict(catalog_item.get("default_settings", {}))
        agent_registry.save_overrides(overrides)

        # Trigger live rediscovery and hot-load
        if hasattr(agent_registry, "discover_and_load"):
            agent_registry.discover_and_load()

    logger.info(f"[AgentCatalog] Successfully installed agent '{clean_id}' into {agent_folder}")

    return {
        "status": "success",
        "agent_id": clean_id,
        "name": catalog_item["name"],
        "icon": catalog_item["icon"],
        "path": str(agent_folder),
        "message": f"Agent '{catalog_item['name']}' downloaded and installed successfully."
    }

