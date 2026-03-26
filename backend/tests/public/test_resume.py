from __future__ import annotations


def test_read_resume_returns_seeded_resume_bundle(client) -> None:
    response = client.get("/api/v1/public/resume")

    assert response.status_code == 200

    payload = response.json()
    assert payload["title"] == "Felix"
    assert payload["subtitle"] == "UI/UX Designer · Frontend Developer"
    assert payload["summary"]
    assert payload["download_label"] == "下载 PDF"
    assert payload["template_key"] == "editorial"
    assert payload["accent_tone"] == "amber"
    assert payload["location"] == "上海 / Remote"
    assert payload["highlights"]
    assert payload["skill_groups"]
    assert payload["experiences"]
    assert payload["skill_groups"][0]["category"] == "Frontend"
    assert payload["experiences"][0]["title"] == "个人网站与设计系统"
    assert payload["experiences"][0]["achievements"]
    assert payload["experiences"][0]["tech_stack"]
