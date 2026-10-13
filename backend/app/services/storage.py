"""Object storage abstraction: S3-compatible (MinIO/AWS) with a local fallback.

Keys follow ``<prefix>/<tenant_id>/<object_id>`` so tenant data is grouped and
easy to enumerate for irreversible deletion.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_LOCAL_ROOT = os.path.join("data", "storage")


class StorageBackend:
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError

    def presigned_url(self, key: str, expires: int = 3600) -> Optional[str]:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, root: str = _LOCAL_ROOT) -> None:
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = key.replace("..", "_").lstrip("/\\")
        path = os.path.join(self.root, safe)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        with open(self._path(key), "wb") as fh:
            fh.write(data)
        return f"/media/{key}"

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as fh:
            return fh.read()

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        base = self._path(prefix)
        target_dir = base if os.path.isdir(base) else os.path.dirname(base.rstrip("/\\"))
        if not os.path.isdir(target_dir):
            return 0
        for root, _dirs, files in os.walk(target_dir):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                    removed += 1
                except OSError:
                    pass
        return removed

    def presigned_url(self, key: str, expires: int = 3600) -> Optional[str]:
        # Served statically by the API (see main.py mount) in local mode.
        return f"/media/{key}"


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"} if settings.s3_force_path_style else {})
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=cfg,
        )
        # Separate client whose endpoint matches the browser-visible host for presign.
        self._public = boto3.client(
            "s3",
            endpoint_url=settings.s3_public_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=cfg,
        )
        self._buckets = {settings.s3_bucket_uploads, settings.s3_bucket_results}
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        for bucket in self._buckets:
            try:
                self._client.head_bucket(Bucket=bucket)
            except Exception:
                try:
                    self._client.create_bucket(Bucket=bucket)
                except Exception as exc:  # pragma: no cover
                    logger.warning("Could not create bucket %s: %s", bucket, exc)

    @staticmethod
    def _bucket_for(key: str) -> str:
        return settings.s3_bucket_results if key.startswith("results/") else settings.s3_bucket_uploads

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(
            Bucket=self._bucket_for(key), Key=key, Body=data, ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return key

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket_for(key), Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket_for(key), Key=key)
        except Exception as exc:  # pragma: no cover
            logger.warning("S3 delete failed for %s: %s", key, exc)

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        for bucket in self._buckets:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if objects:
                    self._client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
                    removed += len(objects)
        return removed

    def presigned_url(self, key: str, expires: int = 3600) -> Optional[str]:
        try:
            return self._public.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_for(key), "Key": key},
                ExpiresIn=expires,
            )
        except Exception:  # pragma: no cover
            return None


_backend: Optional[StorageBackend] = None
_lock = threading.Lock()


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        with _lock:
            if _backend is None:
                if settings.storage_backend.lower() == "local":
                    _backend = LocalStorage()
                else:
                    try:
                        _backend = S3Storage()
                    except Exception as exc:  # pragma: no cover - fallback for dev
                        logger.warning("S3 storage unavailable (%s); falling back to local.", exc)
                        _backend = LocalStorage()
    return _backend
