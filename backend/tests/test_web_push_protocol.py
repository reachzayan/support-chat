"""Independent Node crypto receiver checks the RFC 8291/8292 wire contract."""

import asyncio
import json
import shutil
import subprocess
from types import SimpleNamespace

import httpx

from app.services.web_push import WebPushSender
from app.settings import get_settings
from tests.test_push_notifications import subscription

RECEIVER = r"""
const crypto = require('node:crypto');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const body = Buffer.from(input.body, 'base64');
if (body.readUInt32BE(16) !== 4096 || body[20] !== 65) throw Error('Wrong aes128gcm framing');
const sender = body.subarray(21, 86);
const ecdh = crypto.createECDH('prime256v1');
ecdh.setPrivateKey(Buffer.from('00'.repeat(31) + '07', 'hex'));
const shared = ecdh.computeSecret(sender);
const ikm = crypto.hkdfSync('sha256', shared, Buffer.from('0123456789abcdef'),
  Buffer.concat([Buffer.from('WebPush: info\0'), ecdh.getPublicKey(), sender]), 32);
const key = crypto.hkdfSync('sha256', ikm, body.subarray(0, 16), Buffer.from('Content-Encoding: aes128gcm\0'), 16);
const nonce = crypto.hkdfSync('sha256', ikm, body.subarray(0, 16), Buffer.from('Content-Encoding: nonce\0'), 12);
const decipher = crypto.createDecipheriv('aes-128-gcm', Buffer.from(key), Buffer.from(nonce));
decipher.setAuthTag(body.subarray(-16));
const decrypted = Buffer.concat([decipher.update(body.subarray(86, -16)), decipher.final()]);
if (decrypted.at(-1) !== 2) throw Error('Wrong final record delimiter');
const parts = input.authorization.slice(6).split(', k=');
const token = parts[0].slice(2).split('.');
const point = Buffer.from(parts[1], 'base64url');
const publicKey = crypto.createPublicKey({key: {kty:'EC', crv:'P-256', x:point.subarray(1,33).toString('base64url'), y:point.subarray(33).toString('base64url')}, format:'jwk'});
if (!crypto.verify('sha256', Buffer.from(token.slice(0,2).join('.')), {key:publicKey, dsaEncoding:'ieee-p1363'}, Buffer.from(token[2], 'base64url'))) throw Error('Invalid VAPID signature');
process.stdout.write(JSON.stringify({payload:JSON.parse(decrypted.subarray(0,-1)), claims:JSON.parse(Buffer.from(token[1], 'base64url'))}));
"""


def test_browser_receiver_decrypts_payload_and_verifies_vapid(monkeypatch):
    import base64

    monkeypatch.setenv(
        "PUSH_VAPID_PRIVATE_KEY", base64.urlsafe_b64encode((3).to_bytes(32)).decode().rstrip("=")
    )
    monkeypatch.setenv("PUSH_VAPID_SUBJECT", "mailto:notifications@example.com")
    captured = []

    def accept(request):
        captured.append(request)
        return httpx.Response(201)

    async def send():
        details = subscription()
        device = SimpleNamespace(endpoint=details["endpoint"], **details["keys"])
        async with httpx.AsyncClient(transport=httpx.MockTransport(accept)) as client:
            return await WebPushSender(get_settings(), client).send(
                device, {"title": "Needs attention", "body": "SampleSite"}
            )

    assert asyncio.run(send()) == 201
    request = captured[0]
    assert request.headers["Content-Encoding"] == "aes128gcm"
    assert request.headers["TTL"] == "300"
    node = shutil.which("node")
    assert node is not None, "Node is required for independent Web Push protocol verification"
    received = subprocess.run(
        [node, "-e", RECEIVER],
        input=json.dumps(
            {
                "body": base64.b64encode(request.content).decode(),
                "authorization": request.headers["Authorization"],
            }
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert received.returncode == 0, received.stderr
    result = json.loads(received.stdout)
    assert result["payload"] == {"title": "Needs attention", "body": "SampleSite"}
    assert result["claims"]["aud"] == "https://fcm.googleapis.com"
    assert result["claims"]["sub"] == "mailto:notifications@example.com"
    assert b"SampleSite" not in request.content
