import datetime
import uuid

from google.cloud import storage

from app.config import settings

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=settings.gcp_project_id)
    return _client


def _get_bucket() -> storage.Bucket:
    return _get_client().bucket(settings.gcs_bucket_name)


def generate_upload_url(
    clinic_id: str, purpose: str, object_id: str | None = None, content_type: str = "image/jpeg"
) -> tuple[str, str]:
    if object_id is None:
        object_id = str(uuid.uuid4())

    image_key = f"clinics/{clinic_id}/{purpose}/{object_id}.jpg"
    bucket = _get_bucket()
    blob = bucket.blob(image_key)

    max_size = 10 * 1024 * 1024  # 10 MB
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type=content_type,
        headers={"x-goog-content-length-range": f"0,{max_size}"},
    )

    return url, image_key


def generate_download_url(image_key: str) -> str:
    bucket = _get_bucket()
    blob = bucket.blob(image_key)

    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="GET",
    )


def download_image(image_key: str) -> bytes:
    bucket = _get_bucket()
    blob = bucket.blob(image_key)
    return blob.download_as_bytes()


def upload_image(image_key: str, data: bytes, content_type: str = "image/jpeg") -> None:
    bucket = _get_bucket()
    blob = bucket.blob(image_key)
    blob.upload_from_string(data, content_type=content_type)
