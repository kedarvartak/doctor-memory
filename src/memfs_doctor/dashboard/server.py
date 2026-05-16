from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.resources
import json
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from memfs_doctor.dashboard.service import DashboardService
from memfs_doctor.storage.sqlite import SQLiteEventStore


STATIC_PACKAGE = "memfs_doctor.dashboard.static"


def create_dashboard_server(host: str, port: int, *, store: SQLiteEventStore) -> ThreadingHTTPServer:
    service = DashboardService(store)

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/overview":
                self._write_json(service.overview())
                return
            if path == "/api/sessions":
                self._write_json({"sessions": [item.to_dict() for item in service.list_sessions()]})
                return
            if path.startswith("/api/session/"):
                remainder = path[len("/api/session/") :]
                if remainder.endswith("/snapshots"):
                    session_id = unquote(remainder[: -len("/snapshots")].rstrip("/"))
                    self._write_json({"snapshots": service.session_detail(session_id)["snapshots"]})
                    return
                session_id = unquote(remainder.rstrip("/"))
                self._write_json(service.session_detail(session_id))
                return
            self._serve_static(path)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _write_json(self, payload: dict) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, path: str) -> None:
            asset_name = _resolve_asset_name(path)
            try:
                content = importlib.resources.files(STATIC_PACKAGE).joinpath(asset_name).read_bytes()
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", _content_type(asset_name))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return ThreadingHTTPServer((host, port), DashboardHandler)


def _resolve_asset_name(path: str) -> str:
    normalized = PurePosixPath(path or "/")
    if normalized == PurePosixPath("/") or normalized == PurePosixPath("/index.html"):
        return "index.html"
    asset_name = str(normalized).lstrip("/")
    if asset_name.startswith("api/"):
        return "index.html"
    return asset_name


def _content_type(asset_name: str) -> str:
    if asset_name.endswith(".css"):
        return "text/css; charset=utf-8"
    if asset_name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if asset_name.endswith(".png"):
        return "image/png"
    return "text/html; charset=utf-8"

