from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from aerisun.domain.automation.runtime import invoke_model_json
from aerisun.domain.automation.settings import get_agent_model_config
from aerisun.domain.content.schemas import PoemGenerationRequest, PoemGenerationResponse
from aerisun.domain.exceptions import ValidationError

_MAX_MARKDOWN_CHARS = 6000
_MAX_PLAIN_TEXT_CHARS = 2200
_MARKDOWN_LINE_PREFIX_RE = re.compile(r"^[#>*+\-\d.\)\s]+", flags=re.MULTILINE)


def _strip_markdown_text(value: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", value)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _MARKDOWN_LINE_PREFIX_RE.sub("", text)
    return " ".join(text.split())


def _truncate_text(value: str, *, limit: int) -> str:
    compact = value.strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    return compact or None


def _normalize_poem(value: object) -> str:
    if not isinstance(value, str):
        return ""
    poem = " ".join(value.split())
    poem = poem.replace(" -- ", "——").replace("--", "——")
    return poem.strip(" \n\t\"'")


def generate_diary_poem(session: Session, payload: PoemGenerationRequest) -> PoemGenerationResponse:
    draft_markdown = _normalize_optional_text(payload.body)
    if draft_markdown is None:
        raise ValidationError("请先在 Markdown 编辑框里写一点草稿，再生成诗句。")

    model_config = get_agent_model_config(session)
    if not model_config.is_ready:
        raise ValidationError("请先在 Agent 模型配置中填写可用的 Base URL、模型和 API Key。")
    if model_config.provider != "openai_compatible":
        raise ValidationError(f"暂不支持当前模型提供方：{model_config.provider}")

    plain_text = _strip_markdown_text(draft_markdown)
    if not plain_text:
        raise ValidationError("当前 Markdown 草稿里还没有可供理解的正文内容。")

    request_payload = {
        "task": "根据当前日记草稿挑选一句最应景的中文古典诗句",
        "draft_markdown_excerpt": _truncate_text(draft_markdown, limit=_MAX_MARKDOWN_CHARS),
        "draft_plain_text_excerpt": _truncate_text(plain_text, limit=_MAX_PLAIN_TEXT_CHARS),
        "title": _normalize_optional_text(payload.title),
        "summary": _normalize_optional_text(payload.summary),
        "tags": [item.strip() for item in payload.tags or [] if item and item.strip()],
        "mood": _normalize_optional_text(payload.mood),
        "weather": _normalize_optional_text(payload.weather),
        "custom_requirement": _normalize_optional_text(payload.custom_requirement),
    }

    parsed = invoke_model_json(
        model_config.model_dump(exclude={"is_ready"}),
        messages=[
            {
                "role": "system",
                "content": (
                    "You help a Chinese diary editor choose one fitting classical Chinese poetic line. "
                    "Return strict JSON with keys poem and reason. "
                    "poem must be a single concise Chinese poetic line that best matches the diary draft. "
                    "Prefer widely known classical verses instead of newly invented text. "
                    "When possible, include attribution in the form “诗句。——作者”. "
                    "Do not output markdown, code fences, lists, or extra commentary. "
                    "If custom requirements conflict with the draft, relevance to the draft wins."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(request_payload, ensure_ascii=False),
            },
        ],
    )

    poem = _normalize_poem(parsed.get("poem"))
    if not poem:
        raise ValidationError("AI 没有返回可用的诗句，请稍后重试。")
    return PoemGenerationResponse(poem=poem)
