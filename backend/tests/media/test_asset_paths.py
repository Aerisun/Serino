from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from aerisun.domain.exceptions import ValidationError
from aerisun.domain.media import paths
from aerisun.domain.media.schemas import AssetAdminUpdate, AssetUploadPlanWrite


@pytest.fixture()
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "media"
    monkeypatch.setattr(paths, "get_settings", lambda: SimpleNamespace(media_dir=root))
    return root


def test_asset_paths_keep_canonical_url_separate_from_scope(media_root: Path) -> None:
    identity = paths.AssetIdentity(asset_id="6eb6", extension="webp")

    assert paths.build_resource_key(identity) == "assets/6eb6.webp"
    assert paths.build_media_url(identity) == "/media/assets/6eb6.webp"
    assert paths.build_local_path(identity, "article") == media_root / "assets/article/6eb6.webp"
    assert paths.build_remote_object_key(identity, "article") == "assets/article/6eb6.webp"


def test_category_cannot_affect_asset_paths(media_root: Path) -> None:
    identity = paths.AssetIdentity(asset_id="asset-id", extension="png")

    assert paths.build_resource_key(identity) == "assets/asset-id.png"
    assert paths.build_local_path(identity, "user") == media_root / "assets/user/asset-id.png"
    assert paths.build_remote_object_key(identity, "user") == "assets/user/asset-id.png"


@pytest.mark.parametrize("scope", ["user", "article", "visitor", "system"])
def test_asset_paths_accept_exactly_the_four_managed_scopes(media_root: Path, scope: str) -> None:
    identity = paths.AssetIdentity(asset_id="asset-id", extension="svg")

    assert paths.build_local_path(identity, scope).parent.name == scope
    assert paths.build_remote_object_key(identity, scope).split("/")[1] == scope


@pytest.mark.parametrize("scope", ["", "public", "internal", "../article", "ARTICLE"])
def test_asset_paths_reject_unknown_or_unsafe_scopes(media_root: Path, scope: str) -> None:
    identity = paths.AssetIdentity(asset_id="asset-id", extension="webp")

    with pytest.raises(ValidationError):
        paths.build_local_path(identity, scope)
    with pytest.raises(ValidationError):
        paths.build_remote_object_key(identity, scope)


@pytest.mark.parametrize(
    ("asset_id", "extension"),
    [
        ("", "webp"),
        ("../asset", "webp"),
        ("asset/id", "webp"),
        ("asset", ""),
        ("asset", ".webp"),
        ("asset", "web/p"),
    ],
)
def test_asset_identity_rejects_unsafe_segments(asset_id: str, extension: str) -> None:
    with pytest.raises(ValidationError):
        paths.AssetIdentity(asset_id=asset_id, extension=extension)


def test_managed_path_guards_reject_paths_and_keys_outside_assets_root(media_root: Path, tmp_path: Path) -> None:
    identity = paths.AssetIdentity(asset_id="asset", extension="webp")
    managed_path = paths.build_local_path(identity, "system")
    managed_key = paths.build_remote_object_key(identity, "system")

    assert paths.assert_managed_local_path(managed_path) == managed_path.resolve()
    assert paths.assert_managed_object_key(managed_key) == managed_key

    with pytest.raises(ValidationError):
        paths.assert_managed_local_path(tmp_path / "outside.webp")
    with pytest.raises(ValidationError):
        paths.assert_managed_object_key("internal/assets/system/asset.webp")
    with pytest.raises(ValidationError):
        paths.assert_managed_object_key("assets/system/../asset.webp")


@pytest.mark.parametrize("scope", ["user", "article", "visitor", "system"])
def test_asset_write_schemas_accept_all_managed_scopes(scope: str) -> None:
    upload = AssetUploadPlanWrite(file_name="asset.webp", byte_size=1, sha256="a" * 64, scope=scope)
    update = AssetAdminUpdate(scope=scope)

    assert upload.scope == scope
    assert update.scope == scope


def test_asset_write_schemas_reject_legacy_visibility_directories_as_scopes() -> None:
    with pytest.raises(PydanticValidationError):
        AssetUploadPlanWrite(file_name="asset.webp", byte_size=1, sha256="a" * 64, scope="internal")
