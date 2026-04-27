#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import boto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class UploadAsset:
    source: Path
    key: str
    content_type: str
    cache_control: str | None = None


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def public_url_for_key(key: str) -> str | None:
    base_url = optional_env("BINFEN_INSTALL_BASE_URL")
    public_prefix = optional_env("BINFEN_OSS_PUBLIC_PREFIX").strip("/")
    if not base_url:
        return None

    relative_key = key
    if public_prefix and key == public_prefix:
        relative_key = ""
    elif public_prefix and key.startswith(f"{public_prefix}/"):
        relative_key = key[len(public_prefix) + 1 :]

    encoded_path = "/".join(quote(part) for part in relative_key.split("/") if part)
    return f"{base_url.rstrip('/')}/{encoded_path}" if encoded_path else base_url.rstrip("/")


def public_object_exists(url: str) -> bool:
    for method, headers in (("HEAD", {}), ("GET", {"Range": "bytes=0-0"})):
        request = Request(url, method=method, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                return 200 <= response.status < 400
        except HTTPError as exc:
            if exc.code in {405, 501} and method == "HEAD":
                continue
            return False
        except URLError:
            return False
    return False


def upload_asset(client, bucket: str, asset: UploadAsset) -> None:
    if not asset.source.is_file():
        raise SystemExit(f"Missing installer asset: {asset.source}")

    params = {
        "Bucket": bucket,
        "Key": asset.key,
        "ContentType": asset.content_type,
    }
    if asset.cache_control:
        params["CacheControl"] = asset.cache_control

    try:
        with asset.source.open("rb") as body:
            client.put_object(Body=body, **params)
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "ClientError")
        message = error.get("Message", str(exc))
        fallback_url = public_url_for_key(asset.key)
        if code == "SignatureDoesNotMatch" and fallback_url and public_object_exists(fallback_url):
            print(
                f"upload skipped after SignatureDoesNotMatch; existing object is reachable at {fallback_url}"
            )
            return
        raise SystemExit(
            f"Upload failed for {asset.source} -> s3://{bucket}/{asset.key}: {code}: {message}"
        ) from exc

    print(f"uploaded s3://{bucket}/{asset.key}")


def main() -> int:
    bucket = required_env("BINFEN_OSS_BUCKET")
    endpoint = required_env("BINFEN_OSS_ENDPOINT")
    root_prefix = optional_env("BINFEN_OSS_ROOT_PREFIX")
    version_prefix = required_env("BINFEN_OSS_VERSION_PREFIX")
    dist_dir = Path(optional_env("AERISUN_INSTALLER_DIST_DIR") or "dist/installer")
    region = optional_env("AWS_DEFAULT_REGION") or optional_env("BINFEN_OSS_REGION") or "cn-east-1"
    addressing_style = "path" if optional_env("BINFEN_OSS_FORCE_PATH_STYLE") == "true" else "virtual"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=required_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=required_env("AWS_SECRET_ACCESS_KEY"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": addressing_style},
            # Bitiful rejects the optional checksum headers from recent AWS SDK/CLI defaults.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )

    print(f"boto3 {boto3.__version__} / botocore {botocore.__version__}")

    uploads = [
        UploadAsset(
            dist_dir / "install.latest.sh",
            f"{root_prefix}install.sh",
            "application/x-sh",
            "no-cache, no-store, must-revalidate",
        ),
        UploadAsset(
            dist_dir / "latest.env",
            f"{root_prefix}latest.env",
            "text/plain; charset=utf-8",
            "no-cache, no-store, must-revalidate",
        ),
        UploadAsset(dist_dir / "install.sh", f"{version_prefix}install.sh", "application/x-sh"),
        UploadAsset(
            dist_dir / "aerisun-installer-bundle.tar.gz",
            f"{version_prefix}aerisun-installer-bundle.tar.gz",
            "application/gzip",
        ),
        UploadAsset(
            dist_dir / "aerisun-installer-manifest.env",
            f"{version_prefix}aerisun-installer-manifest.env",
            "text/plain; charset=utf-8",
        ),
        UploadAsset(
            dist_dir / "docker-compose.release.yml",
            f"{version_prefix}docker-compose.release.yml",
            "text/yaml; charset=utf-8",
        ),
        UploadAsset(
            dist_dir / ".env.production.local.example",
            f"{version_prefix}.env.production.local.example",
            "text/plain; charset=utf-8",
        ),
    ]

    for asset in uploads:
        upload_asset(client, bucket, asset)

    return 0


if __name__ == "__main__":
    sys.exit(main())
