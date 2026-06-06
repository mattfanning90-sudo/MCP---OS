"""WhatsApp integrator for mcp-os.

Wraps Meta's official **WhatsApp Business Cloud API** (Graph API) and exposes it
as MCP tools, plus an inbound webhook for receiving messages and delivery
status. Registered onto the FastMCP server via :func:`register`.

Outbound sending requires credentials (set as environment variables):

    WHATSAPP_ACCESS_TOKEN     Permanent or temporary Graph API access token.
    WHATSAPP_PHONE_NUMBER_ID  The Cloud API phone number ID to send from.
    WHATSAPP_API_VERSION      Graph API version (default: v21.0).
    WHATSAPP_GRAPH_BASE       Graph API base URL (default: https://graph.facebook.com).

Inbound webhook (optional) is served at ``/whatsapp/webhook`` and uses:

    WHATSAPP_VERIFY_TOKEN     Shared token echoed back during webhook setup.

Received messages are buffered in memory and read back with the
``whatsapp_get_inbox`` tool.
"""

from __future__ import annotations

import os
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

# In-memory buffer of inbound events (messages + statuses). Bounded so a
# long-running server cannot grow without limit.
_INBOX: deque[dict[str, Any]] = deque(maxlen=500)

MEDIA_TYPES = {"image", "document", "video", "audio"}


class WhatsAppError(RuntimeError):
    """Raised for configuration or API errors from the WhatsApp integrator."""


def _config() -> dict[str, str]:
    """Read send credentials from the environment at call time."""
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        raise WhatsAppError(
            "WhatsApp is not configured for sending. Set WHATSAPP_ACCESS_TOKEN "
            "and WHATSAPP_PHONE_NUMBER_ID."
        )
    version = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
    base = os.environ.get("WHATSAPP_GRAPH_BASE", "https://graph.facebook.com")
    return {
        "token": token,
        "phone_id": phone_id,
        "url": f"{base.rstrip('/')}/{version}/{phone_id}/messages",
    }


def _send(payload: dict[str, Any]) -> str:
    """POST a message payload to the Cloud API and summarize the result."""
    cfg = _config()
    payload = {"messaging_product": "whatsapp", **payload}
    try:
        resp = httpx.post(
            cfg["url"],
            headers={"Authorization": f"Bearer {cfg['token']}"},
            json=payload,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:  # network-level failure
        raise WhatsAppError(f"Request to WhatsApp API failed: {exc}") from exc

    if resp.status_code >= 400:
        raise WhatsAppError(
            f"WhatsApp API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    msg_id = ""
    messages = data.get("messages") or []
    if messages:
        msg_id = messages[0].get("id", "")
    to = ""
    contacts = data.get("contacts") or []
    if contacts:
        to = contacts[0].get("wa_id", "")
    return f"Sent to {to or payload.get('to', '?')} (message id: {msg_id or 'n/a'})."


def _ingest_webhook(body: dict[str, Any]) -> int:
    """Flatten a webhook payload into _INBOX. Returns events recorded."""
    recorded = 0
    received_at = datetime.now(tz=timezone.utc).isoformat()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {
                c.get("wa_id"): (c.get("profile") or {}).get("name")
                for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                sender = msg.get("from")
                mtype = msg.get("type")
                if mtype == "text":
                    content = (msg.get("text") or {}).get("body", "")
                else:
                    # Non-text: keep the type-specific object for context.
                    content = msg.get(mtype, {})
                _INBOX.append(
                    {
                        "kind": "message",
                        "received_at": received_at,
                        "from": sender,
                        "name": contacts.get(sender),
                        "type": mtype,
                        "content": content,
                        "id": msg.get("id"),
                    }
                )
                recorded += 1
            for status in value.get("statuses", []):
                _INBOX.append(
                    {
                        "kind": "status",
                        "received_at": received_at,
                        "id": status.get("id"),
                        "status": status.get("status"),
                        "recipient": status.get("recipient_id"),
                    }
                )
                recorded += 1
    return recorded


def register(mcp) -> None:
    """Register WhatsApp tools and the inbound webhook on a FastMCP server."""

    @mcp.tool()
    def whatsapp_status() -> str:
        """Report whether WhatsApp sending/receiving is configured.

        Does not reveal the access token itself.
        """
        token = bool(os.environ.get("WHATSAPP_ACCESS_TOKEN"))
        phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        verify = bool(os.environ.get("WHATSAPP_VERIFY_TOKEN"))
        return (
            f"send configured: {token and bool(phone_id)}\n"
            f"phone_number_id: {phone_id or '(unset)'}\n"
            f"api_version: {os.environ.get('WHATSAPP_API_VERSION', 'v21.0')}\n"
            f"webhook verify token set: {verify}\n"
            f"buffered inbound events: {len(_INBOX)}"
        )

    @mcp.tool()
    def whatsapp_send_text(to: str, body: str, preview_url: bool = False) -> str:
        """Send a free-form text message.

        Note: outside the 24-hour customer service window, free-form messages
        are rejected by WhatsApp; use whatsapp_send_template to initiate.

        Args:
            to: Recipient phone number in international format (e.g. "15551234567").
            body: Message text.
            preview_url: Render a link preview if the body contains a URL.
        """
        return _send(
            {
                "to": to,
                "type": "text",
                "text": {"preview_url": preview_url, "body": body},
            }
        )

    @mcp.tool()
    def whatsapp_send_template(
        to: str,
        template_name: str,
        language: str = "en_US",
        variables: list[str] | None = None,
    ) -> str:
        """Send a pre-approved template message.

        Required to start a conversation outside the 24-hour window. The
        template must already be approved in WhatsApp Manager.

        Args:
            to: Recipient phone number in international format.
            template_name: Approved template name.
            language: BCP-47 language/locale code, e.g. "en_US".
            variables: Ordered values substituted into the template body
                placeholders ({{1}}, {{2}}, ...). Omit if the template has none.
        """
        template: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language},
        }
        if variables:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(v)} for v in variables
                    ],
                }
            ]
        return _send({"to": to, "type": "template", "template": template})

    @mcp.tool()
    def whatsapp_send_media(
        to: str,
        media_type: str,
        link: str,
        caption: str | None = None,
        filename: str | None = None,
    ) -> str:
        """Send media (image, video, document, or audio) by public URL.

        Args:
            to: Recipient phone number in international format.
            media_type: One of "image", "video", "document", "audio".
            link: Publicly reachable HTTPS URL of the media.
            caption: Optional caption (image, video, and document only).
            filename: Optional display filename (document only).
        """
        media_type = media_type.lower()
        if media_type not in MEDIA_TYPES:
            raise WhatsAppError(
                f"media_type must be one of {sorted(MEDIA_TYPES)}, "
                f"got {media_type!r}."
            )
        media: dict[str, Any] = {"link": link}
        if caption and media_type in {"image", "video", "document"}:
            media["caption"] = caption
        if filename and media_type == "document":
            media["filename"] = filename
        return _send({"to": to, "type": media_type, media_type: media})

    @mcp.tool()
    def whatsapp_get_inbox(limit: int = 20, clear: bool = False) -> str:
        """Return recently received inbound messages and delivery statuses.

        Requires the inbound webhook to be configured and reachable.

        Args:
            limit: Maximum number of most-recent events to return.
            clear: If true, empty the buffer after reading.
        """
        if not _INBOX:
            return "Inbox is empty."
        items = list(_INBOX)[-max(1, limit):]
        lines = []
        for ev in items:
            if ev["kind"] == "message":
                who = ev.get("name") or ev.get("from") or "?"
                lines.append(
                    f"[{ev['received_at']}] {who} ({ev['type']}): {ev['content']}"
                )
            else:
                lines.append(
                    f"[{ev['received_at']}] status: message {ev['id']} "
                    f"-> {ev['status']} (to {ev['recipient']})"
                )
        if clear:
            _INBOX.clear()
        return "\n".join(lines)

    @mcp.custom_route("/whatsapp/webhook", methods=["GET"])
    async def whatsapp_webhook_verify(request: Request) -> Response:
        """Meta webhook verification handshake (GET)."""
        params = request.query_params
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge", "")
        expected = os.environ.get("WHATSAPP_VERIFY_TOKEN")
        if mode == "subscribe" and expected and token == expected:
            return PlainTextResponse(challenge)
        return PlainTextResponse("Verification failed", status_code=403)

    @mcp.custom_route("/whatsapp/webhook", methods=["POST"])
    async def whatsapp_webhook_receive(request: Request) -> Response:
        """Receive inbound message/status notifications (POST)."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)
        count = _ingest_webhook(body)
        return JSONResponse({"received": count})
