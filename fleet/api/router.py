"""
Lightweight Router for Personal Agentic Fleet.
Enables domain-specific API route registration.
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse

logger = logging.getLogger("fleet.api.router")


class _InProcessApiCaptureHandler:
    """In-memory capture handler enabling zero-socket programmatic and MCP invocation of any ApiRouter endpoint."""

    def __init__(self):
        self.status_code: int = 200
        self.response_data: Any = None
        self.headers: Dict[str, str] = {}

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.status_code = int(status)
        self.response_data = data

    def send_error(self, code: int, message: str = "") -> None:
        self.status_code = int(code)
        self.response_data = {"status": "error", "code": int(code), "message": message}

    def send_response(self, code: int) -> None:
        self.status_code = int(code)

    def send_header(self, key: str, val: str) -> None:
        self.headers[key] = val

    def end_headers(self) -> None:
        pass


class ApiRouter:
    """
    HTTP route registry that maps endpoints to handler callables.
    Supports exact matching and prefix routing for dynamic endpoints.
    """

    def __init__(self):
        self.get_routes: Dict[str, Callable] = {}
        self.post_routes: Dict[str, Callable] = {}
        self.get_prefix_routes: List[Tuple[str, Callable]] = []
        self.post_prefix_routes: List[Tuple[str, Callable]] = []

    def get(self, path: str):
        def decorator(fn: Callable):
            self.get_routes[path] = fn
            return fn
        return decorator

    def post(self, path: str):
        def decorator(fn: Callable):
            self.post_routes[path] = fn
            return fn
        return decorator

    def get_prefix(self, prefix: str):
        def decorator(fn: Callable):
            self.get_prefix_routes.append((prefix, fn))
            return fn
        return decorator

    def post_prefix(self, prefix: str):
        def decorator(fn: Callable):
            self.post_prefix_routes.append((prefix, fn))
            return fn
        return decorator

    def include_router(self, other_router: Any):
        """Merges routes from another router or module into this router."""
        if other_router is self or not other_router:
            return
        if hasattr(other_router, "get_routes"):
            self.get_routes.update(other_router.get_routes)
        if hasattr(other_router, "post_routes"):
            self.post_routes.update(other_router.post_routes)
        if hasattr(other_router, "get_prefix_routes"):
            for entry in other_router.get_prefix_routes:
                if entry not in self.get_prefix_routes:
                    self.get_prefix_routes.append(entry)
        if hasattr(other_router, "post_prefix_routes"):
            for entry in other_router.post_prefix_routes:
                if entry not in self.post_prefix_routes:
                    self.post_prefix_routes.append(entry)

    def dispatch_get(self, handler: Any, path: str, parsed_url: urllib.parse.ParseResult) -> bool:
        # 1. Exact match
        fn = self.get_routes.get(path)
        if fn:
            try:
                fn(handler, parsed_url)
            except Exception as e:
                logger.error(
                    "Unhandled exception in API GET %s: %s",
                    path, e,
                    exc_info=True,
                    extra={"action": "api_dispatch_get_error", "agent": "ApiRouter"}
                )
                if hasattr(handler, "_send_json"):
                    handler._send_json({"status": "error", "message": f"Internal API error: {e}"}, status=500)
                else:
                    handler.send_error(500, f"Internal API Error: {e}")
            return True

        # 2. Prefix match
        for prefix, prefix_fn in self.get_prefix_routes:
            if path.startswith(prefix):
                sig = inspect.signature(prefix_fn)
                try:
                    if len(sig.parameters) >= 3:
                        prefix_fn(handler, path, parsed_url)
                    else:
                        prefix_fn(handler, parsed_url)
                except Exception as e:
                    logger.error(
                        "Unhandled exception in API GET prefix %s for path %s: %s",
                        prefix, path, e,
                        exc_info=True,
                        extra={"action": "api_dispatch_get_prefix_error", "agent": "ApiRouter"}
                    )
                    if hasattr(handler, "_send_json"):
                        handler._send_json({"status": "error", "message": f"Internal API error: {e}"}, status=500)
                    else:
                        handler.send_error(500, f"Internal API Error: {e}")
                return True

        return False

    def dispatch_post(self, handler: Any, path: str, body: Dict[str, Any]) -> bool:
        # 1. Exact match
        fn = self.post_routes.get(path)
        if fn:
            try:
                fn(handler, body)
            except Exception as e:
                logger.error(
                    "Unhandled exception in API POST %s: %s",
                    path, e,
                    exc_info=True,
                    extra={"action": "api_dispatch_post_error", "agent": "ApiRouter"}
                )
                if hasattr(handler, "_send_json"):
                    handler._send_json({"status": "error", "message": f"Internal API error: {e}"}, status=500)
                else:
                    handler.send_error(500, f"Internal API Error: {e}")
            return True

        # 2. Prefix match
        for prefix, prefix_fn in self.post_prefix_routes:
            if path.startswith(prefix):
                sig = inspect.signature(prefix_fn)
                try:
                    if len(sig.parameters) >= 3:
                        prefix_fn(handler, path, body)
                    else:
                        prefix_fn(handler, body)
                except Exception as e:
                    logger.error(
                        "Unhandled exception in API POST prefix %s for path %s: %s",
                        prefix, path, e,
                        exc_info=True,
                        extra={"action": "api_dispatch_post_prefix_error", "agent": "ApiRouter"}
                    )
                    if hasattr(handler, "_send_json"):
                        handler._send_json({"status": "error", "message": f"Internal API error: {e}"}, status=500)
                    else:
                        handler.send_error(500, f"Internal API Error: {e}")
                return True

        return False

    def invoke(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Programmatically invokes any registered GET or POST API route in-memory without HTTP socket overhead.
        Used by the Universal FastMCP Bridge (`fleet_call_api`), Event Bus, and Voice/Omnibar routers.
        """
        m = (method or "GET").strip().upper()
        parsed = urllib.parse.urlparse(path or "/")
        clean_path = parsed.path or "/"
        capture = _InProcessApiCaptureHandler()

        if m == "GET":
            matched = self.dispatch_get(capture, clean_path, parsed)
        elif m == "POST":
            matched = self.dispatch_post(capture, clean_path, payload if isinstance(payload, dict) else {})
        else:
            return {"status": "error", "status_code": 405, "message": f"Unsupported HTTP method '{m}'"}

        if not matched:
            return {"status": "error", "status_code": 404, "message": f"API endpoint '{m} {clean_path}' not found"}

        return {
            "status": "ok" if 200 <= capture.status_code < 400 else "error",
            "status_code": capture.status_code,
            "method": m,
            "path": clean_path,
            "data": capture.response_data,
        }

    def list_registered_endpoints(self) -> List[Dict[str, Any]]:
        """Returns a structured catalog of all registered REST API endpoints for OpenAPI & MCP introspection."""
        endpoints: List[Dict[str, Any]] = []
        for path, fn in sorted(self.get_routes.items()):
            endpoints.append({
                "method": "GET",
                "path": path,
                "match_type": "exact",
                "handler": getattr(fn, "__name__", "unknown"),
                "module": getattr(fn, "__module__", ""),
                "description": (inspect.getdoc(fn) or "").split("\n")[0],
            })
        for path, fn in sorted(self.post_routes.items()):
            endpoints.append({
                "method": "POST",
                "path": path,
                "match_type": "exact",
                "handler": getattr(fn, "__name__", "unknown"),
                "module": getattr(fn, "__module__", ""),
                "description": (inspect.getdoc(fn) or "").split("\n")[0],
            })
        for prefix, fn in self.get_prefix_routes:
            endpoints.append({
                "method": "GET",
                "path": f"{prefix}{{param}}",
                "match_type": "prefix",
                "handler": getattr(fn, "__name__", "unknown"),
                "module": getattr(fn, "__module__", ""),
                "description": (inspect.getdoc(fn) or "").split("\n")[0],
            })
        for prefix, fn in self.post_prefix_routes:
            endpoints.append({
                "method": "POST",
                "path": f"{prefix}{{param}}",
                "match_type": "prefix",
                "handler": getattr(fn, "__name__", "unknown"),
                "module": getattr(fn, "__module__", ""),
                "description": (inspect.getdoc(fn) or "").split("\n")[0],
            })
        return endpoints

    def get_openapi_spec(self, version: str = "2.14.3") -> Dict[str, Any]:
        """Generates a live OpenAPI 3.1.0 specification for all registered AFCC & Agentic Fleet endpoints."""
        paths_spec: Dict[str, Dict[str, Any]] = {}
        for ep in self.list_registered_endpoints():
            p = ep["path"]
            m_low = ep["method"].lower()
            paths_spec.setdefault(p, {})[m_low] = {
                "operationId": f"{m_low}_{ep['handler']}_{abs(hash(p)) % 10000}",
                "summary": ep["description"] or f"{ep['method']} {p}",
                "tags": [ep["module"].split(".")[-1] if ep["module"] else "fleet"],
                "responses": {"200": {"description": "JSON response payload"}},
            }
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "Personal Agentic Fleet — API-First & MCP-Ready Microkernel",
                "version": version,
                "description": (
                    "Zero-Token Microkernel REST & FastMCP API for the Agentic Fleet Control Center (AFCC). "
                    "100% Local-First DPAPI Privacy, 12-Layer Security (100/100), Multi-OS (Windows, macOS, Linux), "
                    "Multi-Hyperscaler (Google, Azure, AWS, Claude, Ollama) & Dev Tools (Copilot, Claude Code, Gemini, Amazon Q)."
                ),
                "license": {"name": "Apache 2.0", "url": "https://opensource.org/licenses/Apache-2.0"},
            },
            "paths": paths_spec,
        }


# Global default API router instance
router = ApiRouter()
