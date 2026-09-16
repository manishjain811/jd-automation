import boto3
from pathlib import Path

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    S3_BUCKET,
    S3_PREFIX,
)


class S3Client:

    def __init__(self):

        if not AWS_ACCESS_KEY_ID:
            raise Exception(
                "AWS_ACCESS_KEY_ID is not configured"
            )

        if not AWS_SECRET_ACCESS_KEY:
            raise Exception(
                "AWS_SECRET_ACCESS_KEY is not configured"
            )

        self.bucket = S3_BUCKET
        self.prefix = S3_PREFIX.strip("/")

        self.client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

    def upload_file(self, local_file):

        local_path = Path(local_file)

        if not local_path.exists():
            raise Exception(
                f"File not found: {local_file}"
            )

        s3_key = (
            f"{self.prefix}/"
            f"{local_path.name}"
        )

        print()
        print("=" * 60)
        print("UPLOADING TO S3")
        print("=" * 60)

        print(f"Local file : {local_path}")
        print(f"S3 bucket  : {self.bucket}")
        print(f"S3 key     : {s3_key}")

        self.client.upload_file(
            str(local_path),
            self.bucket,
            s3_key
        )

        s3_url = (
            f"https://{self.bucket}.s3.amazonaws.com/"
            f"{s3_key}"
        )

        print()
        print("✅ S3 upload successful")
        print(f"S3 URL: {s3_url}")

        return s3_url