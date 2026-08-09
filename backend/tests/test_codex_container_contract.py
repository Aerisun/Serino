from pathlib import Path


def test_backend_image_bundles_only_the_pinned_native_codex_runtime() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dockerfile = (project_root / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG CODEX_VERSION=0.147.0" in dockerfile
    assert '"@openai/codex@${CODEX_VERSION}"' in dockerfile
    assert "COPY --from=codex-runtime /opt/codex/codex /usr/local/bin/codex" in dockerfile
    assert "COPY --from=codex-runtime /usr/local/lib/node_modules" not in dockerfile
