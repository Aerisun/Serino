from .state import BOOTSTRAP_MIGRATION_KEY

__all__ = ["BOOTSTRAP_MIGRATION_KEY", "REGISTERED_BACKFILLS", "BackfillSpec", "run_pending_backfills"]


def __getattr__(name: str):
    if name in {"BackfillSpec", "REGISTERED_BACKFILLS"}:
        from .registry import REGISTERED_BACKFILLS, BackfillSpec

        exports = {
            "BackfillSpec": BackfillSpec,
            "REGISTERED_BACKFILLS": REGISTERED_BACKFILLS,
        }
        return exports[name]
    if name == "run_pending_backfills":
        from .runner import run_pending_backfills

        return run_pending_backfills
    raise AttributeError(name)
