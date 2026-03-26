from pydantic import BaseModel


class UploadURLRequest(BaseModel):
    content_type: str
    purpose: str


class UploadURLResponse(BaseModel):
    upload_url: str
    image_key: str


class DownloadURLResponse(BaseModel):
    download_url: str
