from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.automation.schemas import AgentModelConfigUpdate
from aerisun.domain.automation.settings import update_agent_model_config

BASE = "/api/v1/admin/diary/generate-poem"


def _configure_model() -> None:
    factory = get_session_factory()
    with factory() as session:
        update_agent_model_config(
            session,
            AgentModelConfigUpdate(
                base_url="https://model.example/v1",
                model="poem-model",
                api_key="secret-key",
            ),
        )


def test_generate_diary_poem_uses_saved_model_config(client, admin_headers, monkeypatch) -> None:
    _configure_model()
    captured: dict[str, object] = {}

    def fake_invoke(model_config, *, messages):
        captured["model_config"] = model_config
        captured["messages"] = messages
        return {
            "poem": "小楼一夜听春雨，深巷明朝卖杏花。——陆游",
            "reason": "夜雨与草稿氛围相合。",
        }

    monkeypatch.setattr("aerisun.domain.content.poem_generation.invoke_model_json", fake_invoke)

    response = client.post(
        BASE,
        headers=admin_headers,
        json={
            "title": "春夜小记",
            "body": "雨下得很细，窗外的路灯像被雾轻轻包住。\n\n我在灯下补完今天的日记。",
            "mood": "平静",
            "weather": "小雨",
            "custom_requirement": "想要偏清冷一点，但不要太伤感。",
        },
    )

    assert response.status_code == 200
    assert response.json()["poem"] == "小楼一夜听春雨，深巷明朝卖杏花。——陆游"

    model_config = captured["model_config"]
    assert isinstance(model_config, dict)
    assert model_config["base_url"] == "https://model.example/v1"
    assert model_config["model"] == "poem-model"
    assert model_config["api_key"] == "secret-key"

    messages = captured["messages"]
    assert isinstance(messages, list)
    user_payload = next(item["content"] for item in messages if item["role"] == "user")
    assert "春夜小记" in user_payload
    assert "想要偏清冷一点，但不要太伤感。" in user_payload


def test_generate_diary_poem_requires_ready_model_config(client, admin_headers) -> None:
    response = client.post(
        BASE,
        headers=admin_headers,
        json={"body": "今天的晚风很轻。"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "请先在 Agent 模型配置中填写可用的 Base URL、模型和 API Key。"


def test_generate_diary_poem_rejects_empty_body(client, admin_headers, monkeypatch) -> None:
    _configure_model()
    monkeypatch.setattr(
        "aerisun.domain.content.poem_generation.invoke_model_json",
        lambda *args, **kwargs: {"poem": "无效"},
    )

    response = client.post(
        BASE,
        headers=admin_headers,
        json={"body": "   \n\n  "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "请先在 Markdown 编辑框里写一点草稿，再生成诗句。"
