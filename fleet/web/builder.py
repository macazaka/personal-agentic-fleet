"""
Template loader and HTML asset bundler for Personal Agentic Fleet.
Modular web architecture:
- Static assets stored in fleet/web/static/
- HTML templates stored in fleet/web/templates/
Supports both modular HTTP serving (with browser caching) and standalone inlined HTML export.
"""

from pathlib import Path
import re

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"

JS_LOAD_ORDER = [
    "core.js",
    "briefing.js",
    "tasks.js",
    "routines.js",
    "emails.js",
    "antigravity.js",
    "tests.js",
    "backlog.js",
    "optimizer.js",
    "health.js",
    "app.js",
]


def get_dashboard_html(standalone: bool = False) -> str:
    """
    Renders the dashboard HTML.
    - If standalone=True: Inlines CSS and all JS modules into a single self-contained HTML string
      (ideal for offline tests, export, or backwards-compatible HTML_PAGE import).
    - If standalone=False: Returns modular dashboard with /static/css/ and /static/js/ links
      (ideal for browser HTTP caching and token-efficient modular editing).
    """
    tmpl_path = TEMPLATES_DIR / "dashboard.html"
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template not found at {tmpl_path}")

    html = tmpl_path.read_text(encoding="utf-8")

    if not standalone:
        return html

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
