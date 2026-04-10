from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class R2Downloader:
    endpoint_url: str
    bucket_name: str
    access_key_id: str
    secret_access_key: str
    region_name: str = "auto"

    def is_configured(self) -> bool:
        return all(
            (
                self.endpoint_url.strip(),
                self.bucket_name.strip(),
                self.access_key_id.strip(),
                self.secret_access_key.strip(),
            )
        )

    def download(self, object_key: str, destination: Path) -> Path:
        if not self.is_configured():
            raise ValueError("R2 downloader is not configured")

        destination.parent.mkdir(parents=True, exist_ok=True)

        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        client.download_file(self.bucket_name, object_key, str(destination))
        return destination
