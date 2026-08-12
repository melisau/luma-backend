from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageBackend(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_signed_url(self, key: str, expiry_seconds: int) -> str | None:
        raise NotImplementedError


class LocalPrivateStorage(StorageBackend):
    """Local development storage — never mounted as public static files."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        normalized = Path(key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Invalid storage key")
        return self.root / normalized

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def create_signed_url(self, key: str, expiry_seconds: int) -> str | None:
        return None


class S3CompatibleStorage(StorageBackend):
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
    ):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def create_signed_url(self, key: str, expiry_seconds: int) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )


def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not all(
            [
                settings.storage_endpoint,
                settings.storage_bucket,
                settings.storage_access_key_id,
                settings.storage_secret_access_key,
            ]
        ):
            raise RuntimeError("S3 storage selected but credentials are incomplete.")
        return S3CompatibleStorage(
            endpoint=settings.storage_endpoint,
            bucket=settings.storage_bucket,
            access_key=settings.storage_access_key_id,
            secret_key=settings.storage_secret_access_key,
            region=settings.storage_region,
        )
    return LocalPrivateStorage(settings.local_storage_path)
