"""Upload transcript and audio to S3: ai/meets/{date}_{room}_{dmy}_{time}/."""
from typing import Optional

from backend.utils.configs import Config
from backend.utils.logger import CustomLog


def _unique_name(date_ymd: str, meet_code: str, time_hms: str) -> str:
    """Unique name: date (YYYY-MM-DD), room, date DD-MM-YYYY, start time HH-MM-SS."""
    parts = date_ymd.split("-")
    if len(parts) == 3:
        d, m, y = parts[2], parts[1], parts[0]
        date_dmy = f"{d}-{m}-{y}"
    else:
        date_dmy = date_ymd
    time_part = time_hms.replace(":", "-")  # 22:29:56 -> 22-29-56
    return f"{date_ymd}_{meet_code}_{date_dmy}_{time_part}"


def _public_url(bucket: str, key: str, region: str) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


class S3Storage:
    """Upload full transcript and full meeting audio to S3 at ai/meets/<unique_name>/."""

    def __init__(self):
        self._config = Config.load_config()
        self._logger = CustomLog()
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "s3",
                region_name=self._config.aws.REGION,
                **self._config.aws.get_credentials(),
            )
        return self._client

    def _bucket(self) -> Optional[str]:
        return self._config.aws.S3_BUCKET or self._config.aws.S3_BUCKET_PUBLIC

    def is_configured(self) -> bool:
        return bool(self._bucket())

    def upload_audio(
        self,
        webm_path: str,
        date_ymd: str,
        meet_code: str,
        time_hms: str,
    ) -> Optional[str]:
        """Upload full meeting audio (webm) to S3. Key: ai/meets/{unique}/audio.webm"""
        if not self.is_configured():
            self._logger.info("S3 not configured, skip audio upload")
            return None
        bucket = self._bucket()
        unique = _unique_name(date_ymd, meet_code, time_hms)
        key = f"ai/meets/{unique}/audio.webm"
        try:
            with open(webm_path, "rb") as f:
                body = f.read()
            client = self._get_client()
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType="audio/webm",
                ContentDisposition='attachment; filename="audio.webm"',
            )
            self._logger.info(f"Uploaded audio to s3://{bucket}/{key}")
            region = self._config.aws.REGION
            return _public_url(bucket, key, region)
        except Exception as e:
            self._logger.error(f"S3 audio upload failed: {e}", exc_info=True)
            return None

    def upload_transcript(
        self,
        content: str,
        date_ymd: str,
        meet_code: str,
        time_hms: str,
    ) -> Optional[str]:
        """Upload transcript to S3 and return URL. Key: ai/meets/{unique}/full_transcript.txt"""
        if not self.is_configured():
            self._logger.info("S3 not configured, skip upload")
            return None
        bucket = self._bucket()
        unique = _unique_name(date_ymd, meet_code, time_hms)
        key = f"ai/meets/{unique}/full_transcript.txt"
        try:
            client = self._get_client()
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
                ContentDisposition='attachment; filename="full_transcript.txt"',
            )
            self._logger.info(f"Uploaded transcript to s3://{bucket}/{key}")
            region = self._config.aws.REGION
            return _public_url(bucket, key, region)
        except Exception as e:
            self._logger.error(f"S3 upload failed: {e}", exc_info=True)
            return None
