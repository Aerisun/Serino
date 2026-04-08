from __future__ import annotations

import hashlib
import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

import aerisun.core.data_migrations.versions as versions_pkg
from aerisun.core.data_migrations.schema import list_schema_revisions


@dataclass(frozen=True, slots=True)
class DataMigrationSpec:
    migration_key: str
    schema_revision: str
    summary: str
    mode: str
    apply: Callable[[Session], None]
    resource_keys: tuple[str, ...] = ()
    checksum: str = ""
    module_name: str = ""


def _module_checksum(module: object) -> str:
    module_file = getattr(module, "__file__", None)
    if module_file:
        return hashlib.sha256(Path(module_file).read_bytes()).hexdigest()
    return hashlib.sha256(repr(module).encode("utf-8")).hexdigest()


def _spec(module: object) -> DataMigrationSpec:
    mode = str(getattr(module, "mode", "")).strip()
    if mode not in {"blocking", "background"}:
        raise RuntimeError(f"Unsupported data migration mode for {module!r}: {mode!r}")

    migration_key = str(getattr(module, "migration_key", "")).strip()
    schema_revision = str(getattr(module, "schema_revision", "")).strip()
    summary = str(getattr(module, "summary", "")).strip()
    apply = getattr(module, "apply", None)
    if not migration_key or not schema_revision or not summary or not callable(apply):
        raise RuntimeError(f"Invalid data migration module: {getattr(module, '__name__', module)!r}")

    return DataMigrationSpec(
        migration_key=migration_key,
        schema_revision=schema_revision,
        summary=summary,
        mode=mode,
        apply=apply,
        resource_keys=tuple(getattr(module, "resource_keys", ())),
        checksum=_module_checksum(module),
        module_name=str(getattr(module, "__name__", "")),
    )


def get_registered_data_migrations() -> tuple[DataMigrationSpec, ...]:
    active_revisions = list_schema_revisions()
    active_revision_set = set(active_revisions)
    revision_index = {revision: index for index, revision in enumerate(active_revisions)}
    discovered: list[DataMigrationSpec] = []
    seen_keys: set[str] = set()
    seen_schema_revisions: set[str] = set()

    for module_info in pkgutil.iter_modules(versions_pkg.__path__, prefix=f"{versions_pkg.__name__}."):
        module = importlib.import_module(module_info.name)
        spec = _spec(module)
        module_stem = module_info.name.rsplit(".", 1)[-1]
        if not module_stem.startswith(f"{spec.schema_revision}_"):
            raise RuntimeError(
                f"Data migration module {module_info.name} must start with '{spec.schema_revision}_' to match schema."
            )
        if spec.schema_revision not in active_revision_set:
            raise RuntimeError(
                f"Data migration {spec.migration_key} references unknown active schema revision {spec.schema_revision!r}."
            )
        if spec.migration_key in seen_keys:
            raise RuntimeError(f"Duplicate data migration key: {spec.migration_key}")
        if spec.schema_revision in seen_schema_revisions:
            raise RuntimeError(
                f"Only one data migration module is allowed per schema revision; duplicate {spec.schema_revision}."
            )
        seen_keys.add(spec.migration_key)
        seen_schema_revisions.add(spec.schema_revision)
        discovered.append(spec)

    discovered.sort(key=lambda item: (revision_index[item.schema_revision], item.migration_key))
    return tuple(discovered)


REGISTERED_DATA_MIGRATIONS = get_registered_data_migrations()
