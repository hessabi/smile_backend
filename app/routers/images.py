import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_active_subscription
from app.models.user import User
from app.schemas.image import DownloadURLResponse, UploadURLRequest, UploadURLResponse
from app.services.audit import log_action
from app.services.storage import generate_download_url, generate_upload_url

router = APIRouter(prefix="/images", tags=["📸 Images"], dependencies=[Depends(require_active_subscription)])


@router.post("/upload-url", response_model=UploadURLResponse)
async def get_upload_url(
    body: UploadURLRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.purpose not in ("before", "post_procedure"):
        raise HTTPException(status_code=400, detail="Invalid purpose. Must be 'before' or 'post_procedure'.")

    if body.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Invalid content type.")

    object_id = str(uuid.uuid4())
    clinic_id = str(current_user.clinic_id)

    url, image_key = generate_upload_url(
        clinic_id=clinic_id,
        purpose=body.purpose,
        object_id=object_id,
        content_type=body.content_type,
    )

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="image.upload_url_generated",
        resource_type="image",
        details={"image_key": image_key, "purpose": body.purpose},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UploadURLResponse(upload_url=url, image_key=image_key)


@router.get("/{image_key:path}", response_model=DownloadURLResponse)
async def get_download_url(
    image_key: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_prefix = f"clinics/{current_user.clinic_id}/"
    if not image_key.startswith(clinic_prefix):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        url = generate_download_url(image_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="image.download_url_generated",
        resource_type="image",
        details={"image_key": image_key},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return DownloadURLResponse(download_url=url)
