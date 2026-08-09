"""Small, lifecycle-aware client for the official Codex App Server.

The app server owns ChatGPT OAuth storage and token refresh. Serino only keeps
the selected model and account metadata; access and refresh tokens never pass
through the database or admin API.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from aerisun.core.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)

_PROCESS_EOF = object()
_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


class CodexAppServerError(RuntimeError):
    """Base error for Codex App Server operations."""


class CodexAppServerUnavailable(CodexAppServerError):
    """The local app-server process cannot be started or reached."""


class CodexAppServerTimeout(CodexAppServerError):
    """An app-server request exceeded its hard deadline."""


class CodexAppServerProtocolError(CodexAppServerError):
    """The app server returned an error or malformed response."""


class CodexAppServerTurnError(CodexAppServerError):
    """A model turn completed unsuccessfully."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CodexAccount:
    email: str | None
    plan_type: str


@dataclass(frozen=True, slots=True)
class CodexDeviceLogin:
    login_id: str
    verification_url: str
    user_code: str


@dataclass(frozen=True, slots=True)
class CodexLoginStatus:
    status: Literal["pending", "completed", "failed"]
    account: CodexAccount | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CodexModel:
    model: str
    display_name: str
    is_default: bool


def _safe_message(value: object, *, fallback: str) -> str:
    text = redact_sensitive_data(str(value or "")).strip()
    return (text or fallback)[:1000]


def _json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
                break
            except json.JSONDecodeError:
                continue
    if not isinstance(value, dict):
        raise CodexAppServerProtocolError("ChatGPT 未返回有效的 JSON 对象。")
    return value


def _conversation_prompt(messages: list[dict[str, Any]]) -> str:
    sections = [
        "Complete the following model conversation as a structured inference worker.",
        "Return only the JSON value required by the supplied output schema.",
    ]
    for message in messages:
        role = str(message.get("role") or "user").upper()
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        sections.append(f"[{role}]\n{content}")
    return "\n\n".join(sections)


class CodexAppServerClient:
    """Serialize access to one lazily-started, managed-auth app server."""

    def __init__(
        self,
        *,
        executable: str,
        codex_home: Path,
        workspace: Path,
        request_timeout_seconds: float = 10,
        idle_timeout_seconds: float = 300,
        proxy_url_provider: Callable[[], str | None] | None = None,
        require_proxy: bool = False,
    ) -> None:
        self._executable = executable
        self._codex_home = codex_home.expanduser().resolve()
        self._workspace = workspace.expanduser().resolve()
        self._request_timeout_seconds = request_timeout_seconds
        self._idle_timeout_seconds = idle_timeout_seconds
        self._proxy_url_provider = proxy_url_provider
        self._require_proxy = require_proxy
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict[str, Any] | object] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._idle_timer: threading.Timer | None = None
        self._last_activity = 0.0
        self._next_request_id = 1
        self._notifications: deque[dict[str, Any]] = deque(maxlen=256)
        self._login_results: dict[str, tuple[bool, str | None]] = {}
        self._current_login_id: str | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_locked()

    def _is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _prepare_private_directory(self, path: Path) -> None:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            logger.warning("Could not tighten permissions for a Codex runtime directory")

    def _process_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for key in _PROXY_ENV_KEYS:
            environment.pop(key, None)

        proxy_url: str | None = None
        if self._proxy_url_provider is not None:
            try:
                proxy_url = str(self._proxy_url_provider() or "").strip() or None
            except Exception as exc:
                raise CodexAppServerUnavailable(
                    _safe_message(exc, fallback="无法读取 ChatGPT OAuth 代理设置。")
                ) from exc
        if self._require_proxy and proxy_url is None:
            raise CodexAppServerUnavailable("请先在代理设置中填写代理端口并开启 OAuth 代理。")
        if proxy_url is not None:
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                environment[key] = proxy_url

        environment["CODEX_HOME"] = str(self._codex_home)
        environment["NO_COLOR"] = "1"
        environment.pop("OPENAI_API_KEY", None)
        environment.pop("CODEX_API_KEY", None)
        return environment

    def _ensure_process_locked(self) -> None:
        if self._is_running_locked():
            return
        self._stop_process_locked()
        self._prepare_private_directory(self._codex_home)
        self._prepare_private_directory(self._workspace)
        environment = self._process_environment()
        command = [
            self._executable,
            "-c",
            'cli_auth_credentials_store="file"',
            "-c",
            "analytics.enabled=false",
            "app-server",
            "--listen",
            "stdio://",
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=self._workspace,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise CodexAppServerUnavailable(_safe_message(exc, fallback="Codex App Server 无法启动。")) from exc

        message_queue: queue.Queue[dict[str, Any] | object] = queue.Queue()
        self._messages = message_queue
        self._process = process
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            args=(process, message_queue),
            name="codex-app-server-reader",
            daemon=True,
        )
        self._reader_thread.start()
        try:
            self._request_started_locked(
                "initialize",
                {
                    "clientInfo": {"name": "serino", "title": "Serino", "version": "1"},
                    "capabilities": {"experimentalApi": False},
                },
                timeout_seconds=self._request_timeout_seconds,
            )
        except Exception:
            self._stop_process_locked()
            raise

    @staticmethod
    def _read_stdout(
        process: subprocess.Popen[str],
        message_queue: queue.Queue[dict[str, Any] | object],
    ) -> None:
        stdout = process.stdout
        if stdout is None:
            message_queue.put(_PROCESS_EOF)
            return
        try:
            for line in stdout:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Codex App Server emitted an invalid protocol line")
                    continue
                if isinstance(payload, dict):
                    message_queue.put(payload)
        finally:
            message_queue.put(_PROCESS_EOF)

    def _write_locked(self, payload: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            raise CodexAppServerUnavailable("Codex App Server 当前不可用。")
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._stop_process_locked()
            raise CodexAppServerUnavailable("Codex App Server 连接已中断。") from exc

    def _record_notification_locked(self, payload: dict[str, Any]) -> None:
        self._notifications.append(payload)
        if payload.get("method") != "account/login/completed":
            return
        params = payload.get("params")
        if not isinstance(params, dict):
            return
        login_id = str(params.get("loginId") or self._current_login_id or "")
        if login_id:
            success = params.get("success") is True
            error = None if success else _safe_message(params.get("error"), fallback="ChatGPT 登录失败。")
            self._login_results[login_id] = (success, error)

    def _respond_to_server_request_locked(self, payload: dict[str, Any]) -> None:
        if "id" not in payload:
            return
        with suppress(CodexAppServerError):
            self._write_locked(
                {
                    "id": payload["id"],
                    "error": {"code": -32601, "message": "Serino does not expose interactive app-server tools."},
                }
            )

    def _next_message_locked(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._stop_process_locked()
            raise CodexAppServerTimeout("Codex App Server 请求超时。")
        try:
            payload = self._messages.get(timeout=remaining)
        except queue.Empty as exc:
            self._stop_process_locked()
            raise CodexAppServerTimeout("Codex App Server 请求超时。") from exc
        if payload is _PROCESS_EOF:
            self._stop_process_locked()
            raise CodexAppServerUnavailable("Codex App Server 已意外退出。")
        if not isinstance(payload, dict):
            raise CodexAppServerProtocolError("Codex App Server 返回了无效响应。")
        return payload

    def _request_started_locked(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> Any:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._write_locked({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout_seconds
        while True:
            payload = self._next_message_locked(deadline)
            if payload.get("id") == request_id and "method" not in payload:
                if "error" in payload:
                    error = payload.get("error")
                    message = error.get("message") if isinstance(error, dict) else error
                    raise CodexAppServerProtocolError(_safe_message(message, fallback="Codex App Server 请求失败。"))
                return payload.get("result")
            if isinstance(payload.get("method"), str):
                if "id" in payload:
                    self._respond_to_server_request_locked(payload)
                else:
                    self._record_notification_locked(payload)

    def _request_locked(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        self._ensure_process_locked()
        result = self._request_started_locked(
            method,
            params or {},
            timeout_seconds=timeout_seconds or self._request_timeout_seconds,
        )
        self._touch_locked()
        return result

    def _touch_locked(self) -> None:
        self._last_activity = time.monotonic()
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        timer = threading.Timer(self._idle_timeout_seconds, self._close_if_idle)
        timer.daemon = True
        self._idle_timer = timer
        timer.start()

    def _close_if_idle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_activity
            if elapsed >= self._idle_timeout_seconds:
                self._stop_process_locked()
                return
            timer = threading.Timer(self._idle_timeout_seconds - elapsed, self._close_if_idle)
            timer.daemon = True
            self._idle_timer = timer
            timer.start()

    def _stop_process_locked(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin is not None:
            with suppress(OSError):
                process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)

    def close(self) -> None:
        with self._lock:
            self._stop_process_locked()

    @staticmethod
    def _parse_account(result: object) -> CodexAccount | None:
        if not isinstance(result, dict):
            raise CodexAppServerProtocolError("Codex App Server 未返回账号状态。")
        account = result.get("account")
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            return None
        email = account.get("email")
        return CodexAccount(
            email=str(email) if isinstance(email, str) and email else None,
            plan_type=str(account.get("planType") or "unknown"),
        )

    def _read_account_locked(self, *, refresh_token: bool) -> CodexAccount | None:
        result = self._request_locked("account/read", {"refreshToken": refresh_token})
        return self._parse_account(result)

    def read_account(self, *, refresh_token: bool = False) -> CodexAccount | None:
        with self._lock:
            return self._read_account_locked(refresh_token=refresh_token)

    def start_device_login(self) -> CodexDeviceLogin:
        with self._lock:
            result = self._request_locked("account/login/start", {"type": "chatgptDeviceCode"})
            if not isinstance(result, dict) or result.get("type") != "chatgptDeviceCode":
                raise CodexAppServerProtocolError("Codex App Server 未返回设备登录信息。")
            login = CodexDeviceLogin(
                login_id=str(result.get("loginId") or ""),
                verification_url=str(result.get("verificationUrl") or ""),
                user_code=str(result.get("userCode") or ""),
            )
            if not login.login_id or not login.verification_url or not login.user_code:
                raise CodexAppServerProtocolError("ChatGPT 设备登录信息不完整。")
            self._current_login_id = login.login_id
            return login

    def get_login_status(self, login_id: str) -> CodexLoginStatus:
        with self._lock:
            account = self._read_account_locked(refresh_token=False)
            if account is not None:
                return CodexLoginStatus(status="completed", account=account)
            success, error = self._login_results.get(login_id, (False, None))
            if error is not None:
                return CodexLoginStatus(status="failed", error=error)
            if success:
                return CodexLoginStatus(status="completed")
            return CodexLoginStatus(status="pending")

    def logout(self) -> None:
        with self._lock:
            self._request_locked("account/logout")
            self._current_login_id = None
            self._login_results.clear()

    def list_models(self) -> list[CodexModel]:
        with self._lock:
            models: list[CodexModel] = []
            cursor: str | None = None
            for _page in range(10):
                result = self._request_locked(
                    "model/list",
                    {"cursor": cursor, "includeHidden": False, "limit": 100},
                )
                if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                    raise CodexAppServerProtocolError("Codex App Server 未返回模型列表。")
                for item in result["data"]:
                    if not isinstance(item, dict) or item.get("hidden") is True:
                        continue
                    model = str(item.get("model") or item.get("id") or "").strip()
                    if model:
                        models.append(
                            CodexModel(
                                model=model,
                                display_name=str(item.get("displayName") or model),
                                is_default=item.get("isDefault") is True,
                            )
                        )
                next_cursor = result.get("nextCursor")
                if not isinstance(next_cursor, str) or not next_cursor:
                    break
                cursor = next_cursor
            return models

    @staticmethod
    def _turn_error(turn: dict[str, Any]) -> CodexAppServerTurnError:
        error = turn.get("error")
        if not isinstance(error, dict):
            return CodexAppServerTurnError("ChatGPT 模型调用失败。")
        code_value = error.get("codexErrorInfo")
        if isinstance(code_value, str):
            code = code_value
        elif isinstance(code_value, dict) and code_value:
            code = str(next(iter(code_value)))
        else:
            code = None
        return CodexAppServerTurnError(
            _safe_message(error.get("message"), fallback="ChatGPT 模型调用失败。"),
            code=code,
        )

    @staticmethod
    def _collect_agent_message(
        item: object,
        final_messages: list[str],
        fallback_messages: list[str],
    ) -> None:
        if not isinstance(item, dict) or item.get("type") != "agentMessage":
            return
        text = str(item.get("text") or "").strip()
        if not text:
            return
        if item.get("phase") == "final_answer":
            final_messages.append(text)
        elif item.get("phase") != "commentary":
            fallback_messages.append(text)

    def _await_turn_locked(self, *, thread_id: str, turn_id: str, deadline: float) -> str:
        final_messages: list[str] = []
        fallback_messages: list[str] = []
        buffered = list(self._notifications)
        self._notifications.clear()

        while True:
            if buffered:
                payload = buffered.pop(0)
            else:
                payload = self._next_message_locked(deadline)
                if isinstance(payload.get("method"), str) and "id" in payload:
                    self._respond_to_server_request_locked(payload)
                    continue

            method = payload.get("method")
            params = payload.get("params")
            if not isinstance(params, dict):
                continue
            if method == "item/completed":
                if params.get("threadId") == thread_id and params.get("turnId") == turn_id:
                    self._collect_agent_message(params.get("item"), final_messages, fallback_messages)
                else:
                    self._record_notification_locked(payload)
                continue
            if method != "turn/completed":
                self._record_notification_locked(payload)
                continue
            turn = params.get("turn")
            if params.get("threadId") != thread_id or not isinstance(turn, dict) or turn.get("id") != turn_id:
                self._record_notification_locked(payload)
                continue
            for item in turn.get("items") or []:
                self._collect_agent_message(item, final_messages, fallback_messages)
            if turn.get("status") != "completed":
                raise self._turn_error(turn)
            messages = final_messages or fallback_messages
            if not messages:
                raise CodexAppServerProtocolError("ChatGPT 模型未返回最终结果。")
            return messages[-1]

    def run_json(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        output_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        selected_model = model.strip()
        if not selected_model:
            raise CodexAppServerProtocolError("请先选择 ChatGPT 模型。")
        with self._lock:
            thread_id = ""
            try:
                thread_result = self._request_locked(
                    "thread/start",
                    {
                        "model": selected_model,
                        "cwd": str(self._workspace),
                        "approvalPolicy": "never",
                        "sandbox": "read-only",
                        "ephemeral": True,
                        "serviceName": "serino",
                        "developerInstructions": (
                            "Act only as a structured inference worker. Do not run commands, access files, "
                            "browse, call tools, or modify the environment. Return only the requested JSON."
                        ),
                    },
                    timeout_seconds=min(timeout_seconds, self._request_timeout_seconds),
                )
                if not isinstance(thread_result, dict) or not isinstance(thread_result.get("thread"), dict):
                    raise CodexAppServerProtocolError("Codex App Server 未创建模型会话。")
                thread_id = str(thread_result["thread"].get("id") or "")
                if not thread_id:
                    raise CodexAppServerProtocolError("Codex App Server 返回了无效会话。")

                deadline = time.monotonic() + timeout_seconds
                turn_result = self._request_locked(
                    "turn/start",
                    {
                        "threadId": thread_id,
                        "model": selected_model,
                        "input": [{"type": "text", "text": _conversation_prompt(messages)}],
                        "outputSchema": output_schema,
                    },
                    timeout_seconds=max(0.01, deadline - time.monotonic()),
                )
                if not isinstance(turn_result, dict) or not isinstance(turn_result.get("turn"), dict):
                    raise CodexAppServerProtocolError("Codex App Server 未创建模型任务。")
                turn_id = str(turn_result["turn"].get("id") or "")
                if not turn_id:
                    raise CodexAppServerProtocolError("Codex App Server 返回了无效任务。")
                text = self._await_turn_locked(thread_id=thread_id, turn_id=turn_id, deadline=deadline)
                self._touch_locked()
                return _json_object(text)
            finally:
                if thread_id and self._is_running_locked():
                    try:
                        self._request_started_locked(
                            "thread/delete",
                            {"threadId": thread_id},
                            timeout_seconds=min(2, self._request_timeout_seconds),
                        )
                    except CodexAppServerError:
                        logger.warning("Could not delete an ephemeral Codex thread")


_shared_client: CodexAppServerClient | None = None
_shared_client_lock = threading.Lock()


def get_codex_app_server_client() -> CodexAppServerClient:
    global _shared_client
    if _shared_client is not None:
        return _shared_client
    with _shared_client_lock:
        if _shared_client is None:
            from aerisun.core.settings import get_settings

            def configured_oauth_proxy_url() -> str | None:
                from aerisun.core.db import get_session_factory
                from aerisun.domain.outbound_proxy.service import get_outbound_proxy_url

                with get_session_factory()() as session:
                    return get_outbound_proxy_url(session, scope="oauth", required=True)

            settings = get_settings()
            _shared_client = CodexAppServerClient(
                executable=settings.codex_executable,
                codex_home=settings.codex_home,
                workspace=settings.codex_workspace_dir,
                request_timeout_seconds=settings.codex_app_server_request_timeout_seconds,
                idle_timeout_seconds=settings.codex_app_server_idle_timeout_seconds,
                proxy_url_provider=configured_oauth_proxy_url,
                require_proxy=True,
            )
        return _shared_client


def close_codex_app_server_client() -> None:
    global _shared_client
    with _shared_client_lock:
        client = _shared_client
        _shared_client = None
    if client is not None:
        client.close()
