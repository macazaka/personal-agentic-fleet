# Customizing & Operating Agents

The Personal Agentic Fleet provides runtime customization capabilities allowing you to tailor agent behaviors, activate or disable modules without downtime, and install new agents from remote repositories.

---

## Runtime Activation & Deactivation

Agents can be dynamically activated or deactivated directly from the Workstation Control Center:

1. Click the **Settings** gear icon in the top header.
2. Navigate to the **Agent Management** drawer.
3. Toggle the switch next to any agent to enable or disable it immediately.
4. **Zero-Downtime Guarantee**: Disabled agents immediately release background polling timers, database cursors, and system handles without requiring a server reboot.

---

## Dynamic Settings Schema Drawer

Agents declare their customizable fields in `manifest.json` under `custom_settings_schema`. The control center renders these schemas into reactive form controls:

- **String / Text**: Text fields (e.g., API keys, default URLs, city names).
- **Number / Range**: Sliders or numeric inputs (e.g., refresh intervals, batch sizes).
- **Boolean / Toggle**: Switches (e.g., auto-archive emails, enable audio alerts).
- **Select / Dropdown**: Choice menus (e.g., metric vs imperial, logging level).

Settings are encrypted at rest using the OS Credential Vault (NIST SP 800-132 PBKDF2-HMAC-SHA256) and saved in the SQLite key-value store.

---

## Discover & Download Agents from Remote Catalog

Beside the agent list in Settings, click **Discover Agents** to browse the verified remote agent catalog:

- Browse agents by category (Productivity, DevOps, Health, Finance, System).
- Review permissions, author signatures, and SHA-256 hashes.
- Click **Install** to download, unpack, and activate the agent package automatically.

---

## GitHub Version Release Notifications

The Workstation Control Center checks GitHub Releases periodically:

- When a new version is released on GitHub, a banner notification appears in the header.
- Click **View Release Notes** to review changes or **One-Click Upgrade** to stage the update.
