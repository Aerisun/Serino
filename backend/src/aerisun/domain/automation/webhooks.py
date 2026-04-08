"""Webhook subscription management, delivery, and provider-specific formatting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation.models import AutomationEvent, WebhookDelivery, WebhookSubscription
from aerisun.domain.automation.schemas import (
    TelegramWebhookConnectRead,
    WebhookDeadLetterRead,
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.outbound_proxy.service import get_outbound_proxy_request_options

logger = logging.getLogger(__name__)


def list_webhook_subscriptions(session: Session) -> list[WebhookSubscriptionRead]:
    return [WebhookSubscriptionRead.model_validate(item) for item in repo.list_webhook_subscriptions(session)]


def create_webhook_subscription(session: Session, payload: WebhookSubscriptionCreate) -> WebhookSubscriptionRead:
    item = repo.create_webhook_subscription(
        session,
        name=payload.name,
        status=payload.status,
        target_url=payload.target_url,
        secret=payload.secret,
        event_types=payload.event_types,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        headers=payload.headers,
    )
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def test_webhook_subscription(
    session: Session,
    payload: WebhookSubscriptionCreate,
    *,
    subscription_id: str | None = None,
) -> dict[str, Any]:
    subscription = WebhookSubscription(
        name=payload.name or "Webhook test",
        status=payload.status,
        target_url=payload.target_url,
        secret=payload.secret,
        event_types=payload.event_types,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        headers=payload.headers,
    )
    event = AutomationEvent(
        event_type="webhook.test",
        event_id=uuid4().hex,
        target_type="webhook",
        target_id=subscription.name,
        payload={
            "message": "Aerisun webhook test",
            "name": subscription.name,
            "target_url": subscription.target_url,
        },
    )
    target_url, request_payload, headers = _build_webhook_request(subscription, event)
    timeout = httpx.Timeout(float(subscription.timeout_seconds or 10))
    request_options = get_outbound_proxy_request_options(session, scope="webhook")
    try:
        response = httpx.post(
            target_url,
            json=request_payload,
            headers=headers,
            timeout=timeout,
            **request_options,
        )
    except httpx.HTTPError as exc:
        result = {
            "ok": False,
            "provider": _detect_webhook_provider(target_url),
            "target_url": target_url,
            "status_code": None,
            "summary": str(exc),
            "response_body": None,
        }
        _save_webhook_test_result(
            session,
            subscription_id=subscription_id,
            ok=False,
            summary=result["summary"],
        )
        return result

    ok = response.status_code < 400
    summary = "Webhook test succeeded" if ok else f"Webhook returned HTTP {response.status_code}"
    result = {
        "ok": ok,
        "provider": _detect_webhook_provider(target_url),
        "target_url": target_url,
        "status_code": response.status_code,
        "summary": summary,
        "response_body": response.text[:2000],
    }
    _save_webhook_test_result(
        session,
        subscription_id=subscription_id,
        ok=ok,
        summary=summary,
    )
    return result


def _save_webhook_test_result(
    session: Session,
    *,
    subscription_id: str | None,
    ok: bool,
    summary: str,
) -> None:
    if not subscription_id:
        return
    subscription = repo.get_webhook_subscription(session, subscription_id)
    if subscription is None:
        raise ResourceNotFound("Webhook subscription not found")
    subscription.last_test_status = "succeeded" if ok else "failed"
    subscription.last_test_error = None if ok else summary
    subscription.last_tested_at = shanghai_now()
    session.commit()


def connect_telegram_webhook(
    session: Session,
    *,
    bot_token: str,
    send_test_message: bool = True,
) -> TelegramWebhookConnectRead:
    token = str(bot_token or "").strip()
    if not token:
        raise ValidationError("bot_token is required")

    base_url = f"https://api.telegram.org/bot{token}"
    timeout = httpx.Timeout(connect=20.0, read=20.0, write=20.0, pool=20.0)
    request_options = get_outbound_proxy_request_options(session, scope="webhook")

    me_response, me_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/getMe",
        timeout=timeout,
        request_options=request_options,
    )
    if me_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            summary=f"Failed to reach Telegram: {me_error}",
        )
    me_payload = _safe_json_response(me_response)

    if me_response.status_code >= 400 or not me_payload.get("ok"):
        detail = str(me_payload.get("description") or f"HTTP {me_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="invalid_token",
            summary=f"Bot token validation failed: {detail}",
        )

    username = str((me_payload.get("result") or {}).get("username") or "") or None

    delete_response, delete_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/deleteWebhook",
        params={"drop_pending_updates": "false"},
        timeout=timeout,
        request_options=request_options,
    )
    if delete_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            bot_username=username,
            summary=f"Failed to disable webhook mode: {delete_error}",
        )
    delete_payload = _safe_json_response(delete_response)

    if delete_response.status_code >= 400 or not delete_payload.get("ok"):
        detail = str(delete_payload.get("description") or f"HTTP {delete_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="delete_webhook_failed",
            bot_username=username,
            summary=f"Could not switch to getUpdates mode: {detail}",
        )

    updates_response, updates_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/getUpdates",
        params={"offset": -1, "limit": 1, "timeout": 0},
        timeout=timeout,
        request_options=request_options,
    )
    if updates_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            bot_username=username,
            summary=f"Failed to read updates: {updates_error}",
        )
    updates_payload = _safe_json_response(updates_response)

    if updates_response.status_code >= 400 or not updates_payload.get("ok"):
        detail = str(updates_payload.get("description") or f"HTTP {updates_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="get_updates_failed",
            bot_username=username,
            summary=f"Telegram getUpdates failed: {detail}",
        )

    updates = updates_payload.get("result") if isinstance(updates_payload.get("result"), list) else []
    chat_id = _extract_telegram_chat_id(updates)

    if chat_id is None:
        wait_response, wait_error = _telegram_request_with_retry(
            "GET",
            f"{base_url}/getUpdates",
            params={"limit": 1, "timeout": 8},
            timeout=timeout,
            attempts=2,
            request_options=request_options,
        )
        if wait_response is None:
            return TelegramWebhookConnectRead(
                ok=False,
                status="network_error",
                bot_username=username,
                summary=f"Failed while waiting for a new chat message: {wait_error}",
            )
        wait_payload = _safe_json_response(wait_response)

        if wait_response.status_code >= 400 or not wait_payload.get("ok"):
            detail = str(wait_payload.get("description") or f"HTTP {wait_response.status_code}")
            return TelegramWebhookConnectRead(
                ok=False,
                status="get_updates_failed",
                bot_username=username,
                summary=f"Telegram getUpdates failed: {detail}",
            )

        wait_updates = wait_payload.get("result") if isinstance(wait_payload.get("result"), list) else []
        chat_id = _extract_telegram_chat_id(wait_updates)

    if chat_id is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="awaiting_message",
            bot_username=username,
            summary="No recent chat found. Send a message to the bot, then retry connect.",
        )

    target_url = f"{base_url}/sendMessage?chat_id={chat_id}"

    if send_test_message:
        send_response, send_error = _telegram_request_with_retry(
            "POST",
            f"{base_url}/sendMessage",
            json_payload={
                "chat_id": chat_id,
                "text": "Aerisun Telegram connection successful. chat_id is ready.",
            },
            timeout=timeout,
            request_options=request_options,
        )
        if send_response is None:
            return TelegramWebhookConnectRead(
                ok=False,
                status="network_error",
                bot_username=username,
                chat_id=chat_id,
                target_url=target_url,
                summary=f"Could not send verification message: {send_error}",
            )
        send_payload = _safe_json_response(send_response)

        if send_response.status_code >= 400 or not send_payload.get("ok"):
            detail = str(send_payload.get("description") or f"HTTP {send_response.status_code}")
            return TelegramWebhookConnectRead(
                ok=False,
                status="send_test_failed",
                bot_username=username,
                chat_id=chat_id,
                target_url=target_url,
                summary=f"chat_id found but sendMessage failed: {detail}",
            )

    return TelegramWebhookConnectRead(
        ok=True,
        status="connected",
        bot_username=username,
        chat_id=chat_id,
        target_url=target_url,
        summary="Telegram is connected. chat_id has been detected and verified.",
    )


def update_webhook_subscription(
    session: Session,
    *,
    subscription_id: str,
    payload: WebhookSubscriptionUpdate,
) -> WebhookSubscriptionRead:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def delete_webhook_subscription(session: Session, *, subscription_id: str) -> None:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    repo.delete_webhook_subscription(session, item)
    session.commit()


def list_webhook_deliveries(session: Session) -> list[WebhookDeliveryRead]:
    return [WebhookDeliveryRead.model_validate(item) for item in repo.list_webhook_deliveries(session)]


def list_webhook_dead_letters(session: Session) -> list[WebhookDeadLetterRead]:
    return [WebhookDeadLetterRead.model_validate(item) for item in repo.list_webhook_dead_letters(session)]


def replay_dead_letter(session: Session, *, dead_letter_id: str) -> WebhookDeliveryRead:
    dead_letter = repo.get_webhook_dead_letter(session, dead_letter_id)
    if dead_letter is None:
        raise ResourceNotFound("Webhook dead letter not found")
    subscription = repo.get_webhook_subscription(session, dead_letter.subscription_id)
    if subscription is None:
        raise ResourceNotFound("Webhook subscription not found")
    delivery = repo.create_webhook_delivery(
        session,
        subscription=subscription,
        event=AutomationEvent(
            event_type=dead_letter.event_type,
            event_id=dead_letter.event_id,
            target_type=str(dead_letter.payload.get("target_type") or "unknown"),
            target_id=str(dead_letter.payload.get("target_id") or "unknown"),
            payload=dict(dead_letter.payload),
        ),
    )
    repo.delete_webhook_dead_letter(session, dead_letter)
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def trigger_delivery_retry(session: Session, *, delivery_id: str) -> WebhookDeliveryRead:
    delivery = repo.get_webhook_delivery(session, delivery_id)
    if delivery is None:
        raise ResourceNotFound("Webhook delivery not found")
    delivery.status = "pending"
    delivery.next_attempt_at = shanghai_now()
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def dispatch_due_webhooks(session: Session) -> int:
    now = shanghai_now()
    deliveries = repo.list_due_webhook_deliveries(session, now=now)
    processed = 0
    for delivery in deliveries:
        processed += 1
        _deliver_once(session, delivery, now=now)
    return processed


def _deliver_once(session: Session, delivery: WebhookDelivery, *, now: datetime) -> None:
    subscription = repo.get_webhook_subscription(session, delivery.subscription_id)
    if subscription is None:
        delivery.status = "dead_lettered"
        delivery.last_error = "Webhook subscription not found"
        session.commit()
        return

    try:
        target_url, payload, headers = _build_webhook_request(subscription, delivery)
    except (TypeError, ValidationError) as exc:
        delivery.status = "dead_lettered"
        delivery.last_error = str(exc)
        repo.create_dead_letter(session, delivery=delivery, reason="invalid_webhook_request")
        session.commit()
        return

    delivery.status = "delivering"
    delivery.last_attempt_at = now
    delivery.attempt_count += 1
    session.commit()
    timeout = httpx.Timeout(10.0)
    request_options = get_outbound_proxy_request_options(session, scope="webhook")
    try:
        response = httpx.post(target_url, json=payload, headers=headers, timeout=timeout, **request_options)
        delivery.last_response_status = response.status_code
        delivery.last_response_body = response.text[:2000]
        if response.status_code < 400:
            delivery.status = "succeeded"
            delivery.delivered_at = shanghai_now()
        elif response.status_code in {408, 409, 429} or response.status_code >= 500:
            _schedule_retry_or_dead_letter(
                session,
                delivery,
                max_attempts=subscription.max_attempts,
                reason=f"http_{response.status_code}",
            )
            return
        else:
            delivery.status = "dead_lettered"
            delivery.last_error = f"Non-retryable HTTP {response.status_code}"
            repo.create_dead_letter(session, delivery=delivery, reason=f"http_{response.status_code}")
        session.commit()
    except httpx.HTTPError as exc:
        delivery.last_error = str(exc)
        _schedule_retry_or_dead_letter(
            session,
            delivery,
            max_attempts=subscription.max_attempts,
            reason="network_error",
        )


def _schedule_retry_or_dead_letter(
    session: Session,
    delivery: WebhookDelivery,
    *,
    max_attempts: int,
    reason: str,
) -> None:
    if delivery.attempt_count >= max_attempts:
        delivery.status = "dead_lettered"
        repo.create_dead_letter(session, delivery=delivery, reason=reason)
        session.commit()
        return
    backoff = min(30 * (4 ** max(delivery.attempt_count - 1, 0)), 7200)
    delivery.status = "retry_scheduled"
    delivery.next_attempt_at = shanghai_now() + timedelta(seconds=backoff)
    session.commit()


# ---------------------------------------------------------------------------
# HTTP / provider helpers
# ---------------------------------------------------------------------------


def _safe_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_telegram_network_error(error: Exception) -> str:
    message = str(error)
    lower_message = message.lower()
    if "handshake" in lower_message and "timed out" in lower_message:
        return (
            "TLS handshake timed out when connecting to api.telegram.org. "
            "Check outbound network, DNS/firewall rules, or Telegram proxy availability."
        )
    return message


def _telegram_request_with_retry(
    method: str,
    url: str,
    *,
    timeout: httpx.Timeout,
    params: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
    attempts: int = 3,
    request_options: dict[str, object] | None = None,
) -> tuple[httpx.Response | None, str | None]:
    last_error: Exception | None = None

    for attempt in range(max(attempts, 1)):
        try:
            if method == "GET":
                return httpx.get(url, params=params, timeout=timeout, **(request_options or {})), None
            if method == "POST":
                request_kwargs: dict[str, Any] = {
                    "json": json_payload,
                    "timeout": timeout,
                    **(request_options or {}),
                }
                if params:
                    request_kwargs["params"] = params
                return httpx.post(url, **request_kwargs), None
            return None, f"Unsupported method: {method}"
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
                continue
            return None, _format_telegram_network_error(exc)
        except httpx.HTTPError as exc:
            return None, str(exc)

    if last_error is None:
        return None, "Unknown Telegram network error"
    return None, _format_telegram_network_error(last_error)


def _extract_telegram_chat_id(updates: list[dict[str, Any]]) -> int | str | None:
    for update in reversed(updates):
        for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
            chat = (update.get(key) or {}).get("chat")
            if isinstance(chat, dict) and chat.get("id") is not None:
                return chat["id"]
        chat = (update.get("my_chat_member") or {}).get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            return chat["id"]
    return None


def _detect_webhook_provider(target_url: str) -> str:
    parsed = urlparse(target_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "feishu" in host or "larksuite" in host:
        return "feishu"
    if "telegram" in host and "sendmessage" in path:
        return "telegram"
    return "generic"


def _render_webhook_text(event: AutomationEvent, *, max_length: int) -> str:
    payload_text = json.dumps(event.payload, ensure_ascii=False, indent=2, sort_keys=True)
    lines = [
        "Aerisun automation event",
        f"Event: {event.event_type}",
        f"Target: {event.target_type}:{event.target_id}",
        f"Event ID: {event.event_id}",
        "",
        payload_text,
    ]
    text = "\n".join(lines)
    if len(text) <= max_length:
        return text
    return text[: max_length - 18].rstrip() + "\n... (truncated)"


def _sign_feishu_url(target_url: str, secret: str) -> str:
    if not secret:
        return target_url
    parsed = urlparse(target_url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    timestamp = str(int(shanghai_now().timestamp()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    query_items.update(
        {
            "timestamp": timestamp,
            "sign": base64.b64encode(digest).decode("utf-8"),
        }
    )
    return urlunparse(parsed._replace(query=urlencode(query_items)))


def _build_webhook_request(
    subscription,
    delivery: WebhookDelivery | AutomationEvent,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    if isinstance(delivery, AutomationEvent):
        event = delivery
        target_url = str(subscription.target_url or "").strip()
        headers_data = dict(subscription.headers or {})
    else:
        event = AutomationEvent(**dict(delivery.payload or {}))
        target_url = str(delivery.target_url or "").strip()
        headers_data = dict(delivery.headers or {})

    provider = _detect_webhook_provider(target_url)
    headers = {str(key): str(value) for key, value in headers_data.items()}
    headers.setdefault("Content-Type", "application/json")

    if provider == "feishu":
        url = _sign_feishu_url(target_url, str(subscription.secret or "").strip())
        payload = {
            "msg_type": "text",
            "content": {"text": _render_webhook_text(event, max_length=28000)},
        }
        return url, payload, headers

    if provider == "telegram":
        parsed = urlparse(target_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        chat_id = str(query.get("chat_id") or "").strip()
        if not chat_id:
            raise ValidationError("Telegram webhook target_url must include chat_id")
        payload = {
            "chat_id": chat_id,
            "text": _render_webhook_text(event, max_length=3500),
        }
        parse_mode = str(query.get("parse_mode") or "").strip()
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return target_url, payload, headers

    if isinstance(delivery, AutomationEvent):
        return target_url, dict(event.payload or {}), headers

    return target_url, dict(delivery.payload or {}), headers
