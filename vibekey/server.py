import hmac
import json
import mimetypes
import queue
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent.parent / "web"


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, runtime, port=8765):
        super().__init__(("127.0.0.1", port), Handler)
        self.runtime = runtime
        self.token = secrets.token_urlsafe(32)
        self.allowed_hosts = {"127.0.0.1:%d" % self.server_port, "localhost:%d" % self.server_port}
        self.allowed_origins = {"http://" + host for host in self.allowed_hosts}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # No text, secrets or query strings in logs.

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _secure(self, write=False):
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self._send(403, {"error": "Invalid Host"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in self.server.allowed_origins:
            self._send(403, {"error": "Invalid Origin"})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._send(403, {"error": "Cross-site access refused"})
            return False
        if write and not hmac.compare_digest(self.headers.get("X-VibeKey-Token", ""), self.server.token):
            self._send(403, {"error": "Missing write token"})
            return False
        return True

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked requests are unsupported")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Expected application/json")
        length = int(self.headers.get("Content-Length", "-1"))
        if not 0 <= length <= 1048576:
            raise ValueError("Request too large or missing length")
        self.connection.settimeout(5)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("Incomplete request")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object")
        return value

    def do_GET(self):
        try:
            if not self._secure():
                return
            path = urlsplit(self.path).path
            runtime = self.server.runtime
            if path == "/api/applications":
                from .applications import applications
                self._send(200, {"applications": applications()})
                return
            if path == "/api/state":
                self._send(200, dict(runtime.state(), token=self.server.token))
            elif path == "/api/config":
                with runtime.lock:
                    self._send(200, runtime.store.value)
            elif path == "/api/capabilities":
                self._send(200, runtime.capabilities())
            elif path == "/api/events":
                self._events()
            elif path.startswith("/api/"):
                self._send(404, {"error": "Unknown API"})
            else:
                filename = "index.html" if path == "/" else path.lstrip("/")
                resource = (WEB / filename).resolve()
                if WEB.resolve() not in resource.parents or not resource.is_file():
                    self._send(404, {"error": "Not found"})
                    return
                mime = mimetypes.guess_type(str(resource))[0] or "application/octet-stream"
                self._send(200, resource.read_bytes(), mime + "; charset=utf-8")
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True

    def do_PUT(self):
        self._write("PUT")

    def do_POST(self):
        self._write("POST")

    def _write(self, method):
        try:
            if not self._secure(write=True):
                self.close_connection = True
                return
            body = self._body()
            path = urlsplit(self.path).path
            runtime = self.server.runtime
            if method == "PUT" and path == "/api/config":
                runtime.save(body)
            elif method == "POST" and path == "/api/preview":
                runtime.preview(body.get("seconds", 15))
            elif method == "POST" and path == "/api/device/refresh":
                runtime.refresh_requested.set()
            elif method == "POST" and path == "/api/cancel":
                with runtime.lock:
                    runtime.cancel()
            elif method == "POST" and path == "/api/voice/test":
                operation = body.get("operation")
                if operation not in ("start", "stop", "confirm", "cancel"):
                    raise ValueError("Unknown voice operation")
                # An explicit voice test may access the microphone even in simulation.
                getattr(runtime.voice, operation)()
            elif method == "POST" and path == "/api/simulate" and runtime.simulate:
                control = body.get("control")
                if type(body.get("pressed")) is not bool:
                    raise ValueError("pressed must be boolean")
                runtime.control_event(control, body["pressed"], control in ("cw", "ccw"))
            else:
                self._send(404, {"error": "Unknown API"})
                return
            self._send(200, {"ok": True})
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            self.close_connection = True
            self._send(400, {"error": str(exc)})
        except OSError:
            self.close_connection = True
            self._send(500, {"error": "System operation failed; check device permissions and configuration path"})

    def _events(self):
        client = self.server.runtime.bus.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.connection.settimeout(5)
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while not self.server.runtime.stop_event.is_set():
                try:
                    event = client.get(timeout=1)
                    body = "id: %d\ndata: %s\n\n" % (event["id"], json.dumps(event, ensure_ascii=False))
                except queue.Empty:
                    body = ": heartbeat\n\n"
                self.wfile.write(body.encode("utf-8"))
                self.wfile.flush()
        except (OSError, socket.timeout):
            pass
        finally:
            self.server.runtime.bus.unsubscribe(client)
