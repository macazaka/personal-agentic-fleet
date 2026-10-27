"""
CycloneDX v1.5 Software Bill of Materials (SBOM) & Cryptographic Integrity Generator.
Computes SHA-256 digests across all Fleet core modules and plug-and-play agents to
provide verifiable supply-chain provenance.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR, DATA_DIR, VERSION

REPO_ROOT = BASE_DIR.parent
SBOM_FILE = DATA_DIR / "sbom.cdx.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def generate_sbom(repo_root: Path = REPO_ROOT, save_to_disk: bool = True) -> Dict[str, Any]:
    """Generates a CycloneDX 1.5 JSON Software Bill of Materials with SHA-256 component hashes."""
    import re
    active_ver = VERSION
    cfg_path = repo_root / "fleet" / "config.py"
    if cfg_path.is_file():
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', cfg_path.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            active_ver = m.group(1).strip()

    components: List[Dict[str, Any]] = []

    # 1. Core Python modules
    fleet_dir = repo_root / "fleet"
    if fleet_dir.is_dir():
        for py_file in sorted(fleet_dir.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(repo_root).as_posix()
            digest = _sha256_file(py_file)
            components.append({
                "type": "library",
                "name": rel,
                "version": active_ver,
                "scope": "required",
                "hashes": [{"alg": "SHA-256", "content": digest}],
            })

    # 2. Agent Plugin Manifests
    agents_dir = fleet_dir / "agents"
    if agents_dir.is_dir():
        for manifest_path in sorted(agents_dir.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                digest = _sha256_file(manifest_path)
                components.append({
                    "type": "application",
                    "name": f"fleet-agent-{manifest.get('id', manifest_path.parent.name)}",
                    "version": manifest.get("version", "1.0.0"),
                    "description": manifest.get("description", ""),
                    "hashes": [{"alg": "SHA-256", "content": digest}],
                })
            except Exception:
                continue

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "application",
                "name": "personal-agentic-fleet",
                "version": active_ver,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
            },
        },
        "components": components,
        "component_count": len(components),
    }

    if save_to_disk:
        try:
            target_sbom = (repo_root / "fleet" / "data" / "sbom.cdx.json") if repo_root != REPO_ROOT else SBOM_FILE
            target_sbom.parent.mkdir(parents=True, exist_ok=True)
            target_sbom.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8", newline="\n")
        except Exception:
            pass

    return sbom


def main() -> int:
    doc = generate_sbom()
    print(f"Generated CycloneDX 1.5 SBOM with {doc['component_count']} SHA-256 verified components -> {SBOM_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
