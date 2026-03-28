from __future__ import annotations


def build_capability_id(kind: str, name: str) -> str:
    return f"{kind}:{name}"
