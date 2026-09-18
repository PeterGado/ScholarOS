from __future__ import annotations

import hashlib

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError


class S3CompatibleStorage:
    """Object store realization for the "s3" storage backend (`app.core.config.Settings.
    storage_backend`) - satisfies the same `ContentStore` Protocol as `FilesystemStorage`
    structurally, no inheritance, mirroring that module's own dependency-inversion note.

    Built against the plain S3 API (`boto3`'s generic `s3` client, path-style addressing) so it
    works unmodified against any S3-compatible endpoint - real AWS S3, Cloudflare R2, or a local
    endpoint such as `moto`'s mock server - by configuration alone (`s3_endpoint_url`), never a
    code change. Content-addressed exactly like `FilesystemStorage`: identical content produces
    the same key and is written once (06_Physical_Design_Strategy.md §5); an existing key is
    never re-uploaded, checked via a real `head_object` call rather than assumed.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str = "auto",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # Path-style addressing (bucket.s3.amazonaws.com vs s3.amazonaws.com/bucket) is
            # required by most non-AWS S3-compatible endpoints (moto's mock server included);
            # real AWS S3 also accepts it, so this is the one setting that works everywhere.
            config=BotoConfig(s3={"addressing_style": "path"}),
        )

    def save(self, content: bytes, *, extension: str = "") -> str:
        digest = hashlib.sha256(content).hexdigest()
        suffix = f".{extension.lstrip('.')}" if extension else ""
        reference = f"{digest}{suffix}"
        if not self.exists(reference):
            self._client.put_object(Bucket=self._bucket, Key=reference, Body=content)
        return reference

    def read(self, reference: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=reference)
        return response["Body"].read()

    def exists(self, reference: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=reference)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    def delete(self, reference: str) -> None:
        # Mirrors FilesystemStorage.delete's own semantics - a delete of a key that doesn't
        # exist is a no-op, not an error (S3's delete_object already behaves this way natively,
        # unlike FilesystemStorage's explicit existence check, so no extra call is needed here).
        self._client.delete_object(Bucket=self._bucket, Key=reference)
