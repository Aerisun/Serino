See the repository root [README.md](/home/rowan/Study/CodeProject/Project/Aerisun/impl-lite-backend/README.md) for the deploy, backup, and restore instructions.

The active runtime chain currently lives in:

- `src/aerisun/main.py`
- `src/aerisun/api/public.py`
- `src/aerisun/core/db.py`
- `src/aerisun/domain/*/models.py`
- `src/aerisun/core/seed.py`

The legacy `src/aerisun/api/v1`, `src/aerisun/infrastructure`, and parts of
`src/aerisun/modules` are kept only as compatibility shims while the package is
being converged onto that single runtime chain.
