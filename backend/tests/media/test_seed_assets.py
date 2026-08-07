from __future__ import annotations

import hashlib

from aerisun.core.seed_steps.assets import ensure_seed_asset
from aerisun.domain.media import repository as media_repo
from aerisun.domain.media.models import Asset


def test_seed_asset_prefers_matching_public_slug_owner_over_duplicate_fingerprint(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    content = b"same-system-image"
    digest = hashlib.sha256(content).hexdigest()
    source = tmp_path / "hero.webp"
    source.write_bytes(content)
    duplicate = Asset(
        id="duplicate-system-image",
        file_name="hero.webp",
        resource_key="internal/assets/hero-image/duplicate.webp",
        public_slug=None,
        visibility="internal",
        scope="system",
        category="hero-image",
        storage_path=str(tmp_path / "duplicate.webp"),
        sha256=digest,
        byte_size=len(content),
    )
    slug_owner = Asset(
        id="public-system-image",
        file_name="hero.webp",
        resource_key="public/assets/hero-image/public.webp",
        public_slug="legacy-avatar-test",
        visibility="public",
        scope="system",
        category="hero-image",
        storage_path=str(tmp_path / "public.webp"),
        sha256=digest,
        byte_size=len(content),
    )
    seeded_session.add_all([duplicate, slug_owner])
    seeded_session.commit()
    monkeypatch.setattr(media_repo, "find_asset_by_fingerprint", lambda *_args, **_kwargs: duplicate)

    url = ensure_seed_asset(
        seeded_session,
        source_path=source,
        category="hero-image",
        visibility="public",
        public_slug="legacy-avatar-test",
    )

    assert url == "/media/public/assets/hero-image/public.webp"
    assert slug_owner.public_slug == "legacy-avatar-test"
    assert duplicate.public_slug is None
