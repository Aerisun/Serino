from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from aerisun.core.backfills.versions import (
    v20260403_community_config_defaults,
    v20260403_page_copy_defaults,
    v20260403_runtime_config_defaults,
    v20260403_system_asset_references,
    v20260408_shanghai_timestamps,
)


@dataclass(frozen=True, slots=True)
class BackfillSpec:
    migration_key: str
    summary: str
    apply: Callable[[Session], None]
    resource_keys: tuple[str, ...] = ()


def _spec(module: object) -> BackfillSpec:
    module_exports = module  # typed as runtime-export module object
    return BackfillSpec(
        migration_key=module_exports.migration_key,
        summary=module_exports.summary,
        apply=module_exports.apply,
        resource_keys=tuple(getattr(module_exports, "resource_keys", ())),
    )


REGISTERED_BACKFILLS: tuple[BackfillSpec, ...] = (
    _spec(v20260403_page_copy_defaults),
    _spec(v20260403_community_config_defaults),
    _spec(v20260403_system_asset_references),
    _spec(v20260403_runtime_config_defaults),
    _spec(v20260408_shanghai_timestamps),
)
