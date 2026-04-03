from __future__ import annotations

from pathlib import Path


def normalize_seed_profile(seed_profile: str | None) -> str:
    normalized = (seed_profile or "seed").strip().lower().replace("_", "-")
    if normalized in {"seed", "bootstrap", "prod", "production"}:
        return "seed"
    if normalized in {"dev", "dev-seed", "development"}:
        return "dev-seed"
    return normalized or "seed"


def resolve_seed_module_name(seed_profile: str | None) -> str:
    if normalize_seed_profile(seed_profile) == "dev-seed":
        return "aerisun.core.dev_seed"
    return "aerisun.core.seed"


def resolve_seed_path(seed_dir: Path, *, seed_profile: str | None) -> Path:
    filename = "dev_seed.py" if normalize_seed_profile(seed_profile) == "dev-seed" else "seed.py"
    return seed_dir / filename
