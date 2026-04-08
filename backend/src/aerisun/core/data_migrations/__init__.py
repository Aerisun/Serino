__all__ = [
    "DATA_MIGRATIONS_TABLE",
    "DataMigrationSpec",
    "MigrationJournalEntry",
    "REGISTERED_DATA_MIGRATIONS",
    "apply_pending_data_migrations",
    "clear_migration_journal",
    "collect_migration_status",
    "ensure_migration_journal",
    "get_registered_data_migrations",
    "list_migration_entries",
    "schedule_pending_background_data_migrations",
]


def __getattr__(name: str):
    if name in {"DataMigrationSpec", "REGISTERED_DATA_MIGRATIONS", "get_registered_data_migrations"}:
        from .registry import DataMigrationSpec, REGISTERED_DATA_MIGRATIONS, get_registered_data_migrations

        exports = {
            "DataMigrationSpec": DataMigrationSpec,
            "REGISTERED_DATA_MIGRATIONS": REGISTERED_DATA_MIGRATIONS,
            "get_registered_data_migrations": get_registered_data_migrations,
        }
        return exports[name]
    if name in {"apply_pending_data_migrations", "collect_migration_status", "schedule_pending_background_data_migrations"}:
        from .runner import apply_pending_data_migrations, collect_migration_status, schedule_pending_background_data_migrations

        exports = {
            "apply_pending_data_migrations": apply_pending_data_migrations,
            "collect_migration_status": collect_migration_status,
            "schedule_pending_background_data_migrations": schedule_pending_background_data_migrations,
        }
        return exports[name]
    if name in {"DATA_MIGRATIONS_TABLE", "MigrationJournalEntry", "clear_migration_journal", "ensure_migration_journal", "list_migration_entries"}:
        from .state import (
            DATA_MIGRATIONS_TABLE,
            MigrationJournalEntry,
            clear_migration_journal,
            ensure_migration_journal,
            list_migration_entries,
        )

        exports = {
            "DATA_MIGRATIONS_TABLE": DATA_MIGRATIONS_TABLE,
            "MigrationJournalEntry": MigrationJournalEntry,
            "clear_migration_journal": clear_migration_journal,
            "ensure_migration_journal": ensure_migration_journal,
            "list_migration_entries": list_migration_entries,
        }
        return exports[name]
    raise AttributeError(name)
