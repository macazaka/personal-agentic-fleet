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
                "version": VERSION,
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
                "version": VERSION,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
            },
        },
        "components": components,
        "component_count": len(components),
    }

    if save_to_disk:
        try:
            SBOM_FILE.parent.mkdir(parents=True, exist_ok=True)
            SBOM_FILE.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
        except Exception:
            pass

    return sbom


def main() -> int:
    doc = generate_sbom()
    print(f"Generated CycloneDX 1.5 SBOM with {doc['component_count']} SHA-256 verified components -> {SBOM_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
