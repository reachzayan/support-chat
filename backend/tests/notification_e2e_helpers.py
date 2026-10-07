"""Real HTTP/WebSocket/process/TLS harness. No production notification method is mocked."""

import base64
import ipaddress
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.x509.oid import NameOID
from websockets.sync.client import connect

from tests.conftest import TEST_DATABASE_URL
from tests.test_push_notifications import subscription
from tests.test_web_push_protocol import RECEIVER
from tests.ws_helpers import STAFF_ORIGIN, WIDGET_ORIGIN

BACKEND = Path(__file__).resolve().parents[1]


def eventually(check, *, timeout=15):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return check()
        except (AssertionError, httpx.TransportError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def sql(query, parameters=()):
    url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    assert "test" in url.rsplit("/", 1)[-1]
    with psycopg.connect(url) as connection:
        cursor = connection.execute(query, parameters)
        return cursor.fetchall() if cursor.description else []


def make_certificate(directory):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Notification test gateway")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "gateway.pem", directory / "gateway-key.pem"
    cert_path.write_bytes(certificate.public_bytes(Encoding.PEM))
    key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    key_path.chmod(0o600)
    return cert_path, key_path


class GatewayHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        result = subprocess.run(
            [self.server.node, "-e", RECEIVER],
            input=json.dumps(
                {
                    "body": base64.b64encode(body).decode(),
                    "authorization": self.headers["Authorization"],
                }
            ),
            capture_output=True,
            text=True,
            timeout=10,
        )
        try:
            assert result.returncode == 0, result.stderr
            decoded = json.loads(result.stdout)
            assert decoded["claims"]["aud"] == "https://fcm.googleapis.com"
            assert decoded["claims"]["sub"] == "mailto:notifications@example.com"
            assert time.time() < decoded["claims"]["exp"] <= time.time() + 86400
            assert self.headers["Content-Encoding"] == "aes128gcm"
            assert self.headers["TTL"] == "300"
            assert self.headers["Authorization"].split(", k=")[1] == self.server.application_key
            assert b"SampleSite" not in body and b"secret visitor message" not in body
            with self.server.guard:
                statuses = self.server.statuses.get(self.path)
                status = statuses.popleft() if statuses else 201
                self.server.records.append(
                    {"path": self.path, "status": status, "payload": decoded["payload"]}
                )
        except (AssertionError, ValueError, KeyError) as exc:
            with self.server.guard:
                self.server.errors.append(str(exc))
            status = 400
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


class PushGateway:
    def __init__(self, directory):
        self.cert, key = make_certificate(directory)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), GatewayHandler)
        self.server.node = shutil.which("node")
        assert self.server.node, "Node is required for independent push decryption"
        self.server.records, self.server.errors, self.server.statuses = [], [], {}
        self.server.guard = threading.Lock()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.server.server_port

    def respond(self, device, *statuses):
        with self.server.guard:
            self.server.statuses[f"/fcm/send/{device}"] = deque(statuses)

    def received(self, *, accepted=True):
        with self.server.guard:
            assert not self.server.errors, self.server.errors
            return [
                row.copy() for row in self.server.records if not accepted or row["status"] == 201
            ]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class NotificationStack:
    def __init__(self, directory):
        self.gateway = PushGateway(directory)
        self.workers, self.logs = [], []
        self.environment = os.environ | {
            "ENABLE_BACKGROUND_WORKERS": "false",
            "BACKGROUND_JOB_POLL_SECONDS": "0.1",
            "PUSH_VAPID_PRIVATE_KEY": base64.urlsafe_b64encode((3).to_bytes(32))
            .decode()
            .rstrip("="),
            "PUSH_VAPID_SUBJECT": "mailto:notifications@example.com",
            "E2E_PUSH_PORT": str(self.gateway.port),
            "E2E_PUSH_CERT": str(self.gateway.cert),
            "PYTHONPATH": str(BACKEND),
            "RATE_VISITOR_SUBMIT": "200",
            "RATE_VISITOR_SUBMIT_IP": "500",
        }
        port = free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        self.api = self.launch(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            directory / "api.log",
        )
        self.http = httpx.Client(
            base_url=self.base_url, headers={"Host": "localhost:3000"}, timeout=10, trust_env=False
        )
        try:
            eventually(self.ready)
        except BaseException:
            self.close()
            raise

    def launch(self, command, log_path):
        output = log_path.open("w")
        self.logs.append(output)
        return subprocess.Popen(
            command, cwd=BACKEND, env=self.environment, stdout=output, stderr=subprocess.STDOUT
        )

    def ready(self):
        assert self.api.poll() is None, "E2E API exited before starting"
        response = self.http.get("/health")
        assert response.status_code == 200

    def start_worker(self):
        worker = self.launch(
            [sys.executable, "tests/notification_worker_process.py"],
            self.gateway.cert.parent / f"worker-{len(self.logs)}.log",
        )
        self.workers.append(worker)
        return worker

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def login(self, email, password="secret"):
        response = self.http.post(
            "/auth/login",
            headers={"Origin": STAFF_ORIGIN},
            json={"email": email, "password": password},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def preference(self, headers, site_id, scenario, enabled):
        response = self.http.put(
            "/api/notifications/preferences",
            headers=headers,
            json={"site_id": str(site_id), "scenario": scenario, "in_app": enabled},
        )
        assert response.status_code == 200, response.text

    def subscribe(self, headers, name, *, silent=False):
        config = self.http.get("/api/notifications/push/config", headers=headers)
        assert config.status_code == 200 and config.json()["configured"] is True
        self.gateway.server.application_key = config.json()["public_key"]
        payload = subscription(f"https://fcm.googleapis.com/fcm/send/{name}", silent)
        response = self.http.post(
            "/api/notifications/push/subscriptions", headers=headers, json=payload
        )
        assert response.status_code == 200, response.text
        return response.json()["id"], payload["endpoint"]

    def feed(self, headers, suffix=""):
        response = self.http.get(f"/api/notifications{suffix}", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    @contextmanager
    def agent(self, headers):
        with connect(
            self.base_url.replace("http:", "ws:") + "/ws/agent", origin=STAFF_ORIGIN
        ) as socket:
            send(socket, type="auth", access_token=headers["Authorization"][7:])
            send(socket, type="ping")
            receive(socket, "pong")
            yield socket

    @contextmanager
    def visitor(self, site_key, public_key):
        response = self.http.post(
            "/api/public/widget-bootstrap",
            headers={"Host": "widget.localhost:3000", "Origin": STAFF_ORIGIN},
            json={"site_key": site_key, "public_key": public_key},
        )
        assert response.status_code == 200, response.text
        with connect(
            self.base_url.replace("http:", "ws:") + "/ws/visitor", origin=WIDGET_ORIGIN
        ) as socket:
            send(
                socket,
                type="auth",
                bootstrap_token=response.json()["bootstrap_token"],
                parent_origin=STAFF_ORIGIN,
            )
            receive(socket, "state")
            yield socket

    def close(self):
        for worker in self.workers:
            self.stop_process(worker)
        self.stop_process(self.api)
        self.http.close()
        self.gateway.close()
        for output in self.logs:
            output.close()


def send(socket, **frame):
    socket.send(json.dumps({"v": 1, **frame}))


def receive(socket, kind, **expected):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        frame = json.loads(socket.recv(timeout=max(0.1, deadline - time.monotonic())))
        assert frame.get("type") != "error", frame
        if frame.get("type") == kind and all(
            frame.get(key) == value for key, value in expected.items()
        ):
            return frame
    raise AssertionError(f"Did not receive {kind}")


def prechat(socket):
    import uuid

    send(
        socket,
        type="prechat",
        submission_id=str(uuid.uuid4()),
        name="Test Visitor",
        email="visitor@example.com",
        phone="",
        inquiry_type="other",
        message="",
    )
    state = receive(socket, "state")
    receive(socket, "prechat_accepted")
    return state["conversation_id"]


def drained():
    assert sql("SELECT count(*) FROM push_deliveries WHERE finished_at IS NULL")[0][0] == 0
