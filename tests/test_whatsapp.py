"""Tests for the WhatsApp integrator.

Outbound calls are exercised by capturing the payload that would be POSTed to
the Graph API (httpx.post is monkeypatched), so no network or credentials are
needed. Inbound handling is tested directly against the buffer.
"""

import importlib

import pytest


@pytest.fixture()
def wa(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "111222333")
    import mcp_os.whatsapp as whatsapp

    importlib.reload(whatsapp)
    whatsapp._INBOX.clear()
    return whatsapp


class _FakeResponse:
    status_code = 200
    text = "ok"

    def json(self):
        return {
            "messages": [{"id": "wamid.TEST"}],
            "contacts": [{"wa_id": "15551234567"}],
        }


def _capture(monkeypatch, whatsapp):
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"] = url
        sent["headers"] = headers
        sent["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(whatsapp.httpx, "post", fake_post)
    return sent


def test_config_required(monkeypatch):
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    import mcp_os.whatsapp as whatsapp

    importlib.reload(whatsapp)
    with pytest.raises(whatsapp.WhatsAppError):
        whatsapp._send({"to": "x", "type": "text", "text": {"body": "hi"}})


def test_send_text_payload(wa, monkeypatch):
    sent = _capture(monkeypatch, wa)
    result = wa._send(
        {"to": "15551234567", "type": "text", "text": {"body": "hi"}}
    )
    assert "wamid.TEST" in result
    assert sent["json"]["messaging_product"] == "whatsapp"
    assert sent["json"]["text"]["body"] == "hi"
    assert sent["headers"]["Authorization"] == "Bearer test-token"
    assert "111222333/messages" in sent["url"]


def test_template_payload_with_variables(wa, monkeypatch):
    sent = _capture(monkeypatch, wa)
    # Build the payload exactly as the tool does.
    template = {
        "name": "order_update",
        "language": {"code": "en_US"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "A12"},
                    {"type": "text", "text": "shipped"},
                ],
            }
        ],
    }
    wa._send({"to": "1555", "type": "template", "template": template})
    params = sent["json"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["A12", "shipped"]


def test_api_error_raises(wa, monkeypatch):
    class _Err:
        status_code = 400
        text = '{"error":"bad"}'

        def json(self):
            return {}

    monkeypatch.setattr(wa.httpx, "post", lambda *a, **k: _Err())
    with pytest.raises(wa.WhatsAppError):
        wa._send({"to": "x", "type": "text", "text": {"body": "hi"}})


def test_ingest_inbound_message(wa):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {"wa_id": "1555", "profile": {"name": "Sam"}}
                            ],
                            "messages": [
                                {
                                    "from": "1555",
                                    "id": "wamid.IN",
                                    "type": "text",
                                    "text": {"body": "hello back"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    assert wa._ingest_webhook(payload) == 1
    ev = wa._INBOX[-1]
    assert ev["kind"] == "message"
    assert ev["name"] == "Sam"
    assert ev["content"] == "hello back"


def test_ingest_status(wa):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.OUT",
                                    "status": "delivered",
                                    "recipient_id": "1555",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    assert wa._ingest_webhook(payload) == 1
    assert wa._INBOX[-1]["status"] == "delivered"
