"""
Lightweight Router for Personal Agentic Fleet.
Enables domain-specific API route registration.
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Tuple
import urllib.parse

logger = logging.getLogger("fleet.api.router")


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
            self.get_prefix_routes.extend(other_router.get_prefix_routes)
        if hasattr(other_router, "post_prefix_routes"):
            self.post_prefix_routes.extend(other_router.post_prefix_routes)

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


# Global default API router instance
router = ApiRouter()
