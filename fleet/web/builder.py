"""
Template loader and HTML asset bundler for Personal Agentic Fleet.
Modular web architecture:
- Static assets stored in fleet/web/static/
- HTML templates stored in fleet/web/templates/
Supports both modular HTTP serving (with browser caching) and standalone inlined HTML export.
"""

from pathlib import Path
import re
import threading
from typing import Any, Dict

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"

_MODULAR_HTML_CACHE: Dict[str, Any] = {
    "sig": None,
    "html": None,
    "hits": 0,
    "misses": 0,
}
_BUILDER_CACHE_LOCK = threading.Lock()


def get_builder_cache_stats() -> Dict[str, Any]:
    """Returns cache statistics for dashboard HTML assembly."""
    with _BUILDER_CACHE_LOCK:
        return {
            "hits": int(_MODULAR_HTML_CACHE.get("hits", 0)),
            "misses": int(_MODULAR_HTML_CACHE.get("misses", 0)),
            "cached": _MODULAR_HTML_CACHE.get("html") is not None,
        }


def invalidate_builder_cache() -> None:
    """Clears the cached modular HTML template."""
    with _BUILDER_CACHE_LOCK:
        _MODULAR_HTML_CACHE["sig"] = None
        _MODULAR_HTML_CACHE["html"] = None

JS_LOAD_ORDER = [
    "core.js",
    "briefing.js",
    "tasks.js",
    "routines.js",
    "schedules.js",
    "emails.js",
    "antigravity.js",
    "tests.js",
    "backlog.js",
    "optimizer.js",
    "health.js",
    "settings.js",
    "create_agent.js",
    "fleet_navigator.js",
    "app.js",
]


def _compute_modular_sig(tmpl_path: Path):
    mtimes = []
    try:
        mtimes.append(tmpl_path.stat().st_mtime_ns if tmpl_path.exists() else 0)
        css_file = STATIC_DIR / "css" / "dashboard.css"
        mtimes.append(css_file.stat().st_mtime_ns if css_file.exists() else 0)
        for js_name in JS_LOAD_ORDER:
            js_file = STATIC_DIR / "js" / js_name
            mtimes.append(js_file.stat().st_mtime_ns if js_file.exists() else 0)
    except OSError:
        return None
    return tuple(mtimes)


def get_dashboard_html(standalone: bool = False) -> str:
    """
    Renders the dashboard HTML.
    - If standalone=True: Inlines CSS and all JS modules into a single self-contained HTML string
      (ideal for offline tests, export, or backwards-compatible HTML_PAGE import).
    - If standalone=False: Returns mtime-memoized modular dashboard with /static/css/ and /static/js/ links
      (ideal for browser HTTP caching and zero per-request disk reads).
    """
    tmpl_path = TEMPLATES_DIR / "dashboard.html"
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template not found at {tmpl_path}")

    if not standalone:
        sig = _compute_modular_sig(tmpl_path)
        if sig is not None:
            with _BUILDER_CACHE_LOCK:
                if _MODULAR_HTML_CACHE["sig"] == sig and _MODULAR_HTML_CACHE["html"] is not None:
                    _MODULAR_HTML_CACHE["hits"] += 1
                    return _MODULAR_HTML_CACHE["html"]

        html = tmpl_path.read_text(encoding="utf-8")
        try:
            css_file = STATIC_DIR / "css" / "dashboard.css"
            css_ver = int(css_file.stat().st_mtime) if css_file.exists() else 1
            html = html.replace(
                'href="/static/css/dashboard.css"',
                f'href="/static/css/dashboard.css?v={css_ver}"',
            )
            for js_name in JS_LOAD_ORDER:
                js_file = STATIC_DIR / "js" / js_name
                js_ver = int(js_file.stat().st_mtime) if js_file.exists() else 1
                html = html.replace(
                    f'src="/static/js/{js_name}"',
                    f'src="/static/js/{js_name}?v={js_ver}"',
                )
        except OSError:
            pass
        if sig is not None:
            with _BUILDER_CACHE_LOCK:
                _MODULAR_HTML_CACHE["sig"] = sig
                _MODULAR_HTML_CACHE["html"] = html
                _MODULAR_HTML_CACHE["misses"] += 1
        return html

    html = tmpl_path.read_text(encoding="utf-8")

    # In standalone mode, inline the CSS
    css_path = STATIC_DIR / "css" / "dashboard.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    html = html.replace(
        '<link rel="stylesheet" href="/static/css/dashboard.css">',
        f"<style>\n{css_content}\n</style>"
    )

    # Inline all JS modules in dependency order
    combined_js = []
    for js_name in JS_LOAD_ORDER:
        p = STATIC_DIR / "js" / js_name
        if p.exists():
            combined_js.append(f"// === {js_name} ===\n" + p.read_text(encoding="utf-8"))

    combined_js_code = "\n\n".join(combined_js)

    # Replace the modular script tags with a single inlined <script> block
    scripts_pattern = r'<!-- Modular Client Engines -->.*?<script src="/static/js/app\.js"></script>'
    html = re.sub(
        scripts_pattern,
        lambda m: f"<script>\n{combined_js_code}\n</script>",
        html,
        flags=re.DOTALL
    )

    return html
