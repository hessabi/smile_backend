import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.subscription import require_active_subscription
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.post_procedure import PostProcedureImage
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.simulation import (
    FullSimulationResponse,
    SendEmailRequest,
    SimulationCreate,
    SimulationResponse,
)
from app.services.audit import log_action
from app.services.gemini import generate_smile
from app.services.storage import download_image, generate_download_url, upload_image

router = APIRouter(tags=["😁 Simulations"], dependencies=[Depends(require_active_subscription)])


async def _get_simulation_response(sim: Simulation) -> SimulationResponse:
    resp = SimulationResponse.model_validate(sim)
    try:
        resp.before_image_url = generate_download_url(sim.before_image_key)
    except Exception:
        resp.before_image_url = None
    if sim.result_image_key:
        try:
            resp.result_image_url = generate_download_url(sim.result_image_key)
        except Exception:
            resp.result_image_url = None
    return resp


@router.post("/simulations", response_model=SimulationResponse, status_code=201)
async def create_simulation(
    body: SimulationCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = current_user.clinic_id
    clinic_prefix = f"clinics/{clinic_id}/"

    result = await db.execute(
        select(Patient).where(
            Patient.id == body.patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")

    if not body.before_image_key.startswith(clinic_prefix):
        raise HTTPException(status_code=403, detail="Invalid image key")

    if body.treatment_type not in ("veneers", "whitening", "allon4", "makeover"):
        raise HTTPException(status_code=400, detail="Invalid treatment type")
    if body.shade not in ("subtle", "natural", "hollywood"):
        raise HTTPException(status_code=400, detail="Invalid shade")

    # Trial daily limit check
    clinic_result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = clinic_result.scalar_one_or_none()
    if clinic and clinic.subscription_status == "trial":
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await db.execute(
            select(func.count()).where(
                Simulation.clinic_id == clinic_id,
                Simulation.created_at >= today_start,
            )
        )
        today_count = count_result.scalar() or 0
        if today_count >= settings.trial_daily_simulation_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Trial accounts are limited to {settings.trial_daily_simulation_limit} simulation(s) per day. Subscribe for unlimited access.",
            )

    sim = Simulation(
        clinic_id=clinic_id,
        patient_id=body.patient_id,
        created_by=current_user.id,
        treatment_type=body.treatment_type,
        shade=body.shade,
        before_image_key=body.before_image_key,
        status="processing",
        model_version="gemini-3.1-flash-image-preview",
    )
    db.add(sim)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=current_user.id,
        action="simulation.create",
        resource_type="simulation",
        resource_id=sim.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    try:
        image_data = download_image(body.before_image_key)
    except Exception:
        sim.status = "failed"
        sim.error_message = "Could not retrieve the uploaded photo. Please try again."
        await db.commit()
        return await _get_simulation_response(sim)

    result = await generate_smile(image_data, body.treatment_type, body.shade)
    sim.prompt_used = result.prompt
    sim.generation_time_ms = result.elapsed_ms

    if result.error or result.image_bytes is None:
        sim.status = "failed"
        sim.error_message = result.error or "Could not generate preview."

        await log_action(
            db,
            clinic_id=clinic_id,
            user_id=current_user.id,
            action="simulation.fail",
            resource_type="simulation",
            resource_id=sim.id,
            details={"error": sim.error_message, "elapsed_ms": result.elapsed_ms},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await db.commit()
        return await _get_simulation_response(sim)

    result_key = f"clinics/{clinic_id}/results/{sim.id}.jpg"
    try:
        upload_image(result_key, result.image_bytes)
    except Exception:
        sim.status = "failed"
        sim.error_message = "Failed to save result image. Please try again."
        await db.commit()
        return await _get_simulation_response(sim)

    sim.status = "completed"
    sim.result_image_key = result_key

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=current_user.id,
        action="simulation.complete",
        resource_type="simulation",
        resource_id=sim.id,
        details={"elapsed_ms": result.elapsed_ms},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return await _get_simulation_response(sim)


@router.get("/simulations/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return await _get_simulation_response(sim)


@router.get("/simulations/{simulation_id}/full", response_model=FullSimulationResponse)
async def get_simulation_full(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    base_resp = await _get_simulation_response(sim)
    resp = FullSimulationResponse(**base_resp.model_dump())

    post_proc_result = await db.execute(
        select(PostProcedureImage)
        .where(
            PostProcedureImage.simulation_id == simulation_id,
            PostProcedureImage.clinic_id == current_user.clinic_id,
        )
        .order_by(PostProcedureImage.created_at.desc())
        .limit(1)
    )
    post_proc = post_proc_result.scalar_one_or_none()
    if post_proc:
        try:
            resp.post_procedure_image_url = generate_download_url(post_proc.image_key)
        except Exception:
            resp.post_procedure_image_url = None

    return resp


@router.get("/simulations/{simulation_id}/pdf")
async def get_simulation_pdf(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim.status != "completed":
        raise HTTPException(status_code=400, detail="Can only generate PDF for completed simulations")

    clinic_result = await db.execute(select(Clinic).where(Clinic.id == sim.clinic_id))
    clinic = clinic_result.scalar_one_or_none()

    provider_result = await db.execute(select(User).where(User.id == sim.created_by))
    provider = provider_result.scalar_one_or_none()

    patient_result = await db.execute(select(Patient).where(Patient.id == sim.patient_id))
    patient = patient_result.scalar_one_or_none()

    post_proc_key = None
    post_proc_result = await db.execute(
        select(PostProcedureImage)
        .where(
            PostProcedureImage.simulation_id == simulation_id,
            PostProcedureImage.clinic_id == current_user.clinic_id,
        )
        .order_by(PostProcedureImage.created_at.desc())
        .limit(1)
    )
    post_proc = post_proc_result.scalar_one_or_none()
    if post_proc:
        post_proc_key = post_proc.image_key

    from app.services.pdf import generate_simulation_pdf

    pdf_bytes = generate_simulation_pdf(
        clinic_name=clinic.name if clinic else "Unknown Clinic",
        provider_name=provider.name if provider else "Unknown Provider",
        patient_name=patient.display_name if patient else "Unknown Patient",
        treatment_type=sim.treatment_type,
        shade=sim.shade,
        created_at=sim.created_at,
        before_image_key=sim.before_image_key,
        result_image_key=sim.result_image_key,
        post_procedure_image_key=post_proc_key,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=smile-preview-{simulation_id}.pdf"},
    )


@router.post("/simulations/{simulation_id}/send-email")
async def send_simulation_email(
    simulation_id: uuid.UUID,
    body: SendEmailRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if sim.status != "completed":
        raise HTTPException(status_code=400, detail="Can only email completed simulations")

    patient_result = await db.execute(select(Patient).where(Patient.id == sim.patient_id))
    patient = patient_result.scalar_one_or_none()

    to_email = body.email or (patient.email if patient else None)
    if not to_email:
        raise HTTPException(status_code=400, detail="No email address provided and patient has no email on file")

    clinic_result = await db.execute(select(Clinic).where(Clinic.id == sim.clinic_id))
    clinic = clinic_result.scalar_one_or_none()

    # Generate share token for the email link
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.models.share_token import ShareToken

    token_str = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    share_token = ShareToken(
        simulation_id=simulation_id,
        token=token_str,
        expires_at=expires_at,
        created_by=current_user.id,
    )
    db.add(share_token)
    await db.flush()

    from app.config import settings

    share_url = f"{settings.share_base_url}/share/{token_str}"

    # Generate signed URLs for email inline images
    before_url = None
    preview_url = None
    try:
        before_url = generate_download_url(sim.before_image_key)
    except Exception:
        pass
    if sim.result_image_key:
        try:
            preview_url = generate_download_url(sim.result_image_key)
        except Exception:
            pass

    # Generate PDF attachment
    post_proc_key = None
    post_proc_result = await db.execute(
        select(PostProcedureImage)
        .where(
            PostProcedureImage.simulation_id == simulation_id,
            PostProcedureImage.clinic_id == current_user.clinic_id,
        )
        .order_by(PostProcedureImage.created_at.desc())
        .limit(1)
    )
    post_proc = post_proc_result.scalar_one_or_none()
    if post_proc:
        post_proc_key = post_proc.image_key

    from app.services.pdf import generate_simulation_pdf

    pdf_bytes = generate_simulation_pdf(
        clinic_name=clinic.name if clinic else "Unknown Clinic",
        provider_name=current_user.name,
        patient_name=patient.display_name if patient else "Patient",
        treatment_type=sim.treatment_type,
        shade=sim.shade,
        created_at=sim.created_at,
        before_image_key=sim.before_image_key,
        result_image_key=sim.result_image_key,
        post_procedure_image_key=post_proc_key,
    )

    from app.services.email import send_share_email

    sent = send_share_email(
        to_email=to_email,
        patient_name=patient.display_name if patient else "Patient",
        clinic_name=clinic.name if clinic else "Unknown Clinic",
        provider_name=current_user.name,
        treatment_type=sim.treatment_type,
        share_url=share_url,
        before_image_url=before_url,
        preview_image_url=preview_url,
        pdf_bytes=pdf_bytes,
    )

    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again.")

    await log_action(
        db,
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        action="simulation.email_sent",
        resource_type="simulation",
        resource_id=simulation_id,
        details={"to_email": to_email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"detail": "Email sent successfully", "to": to_email}


@router.get("/patients/{patient_id}/simulations", response_model=list[SimulationResponse])
async def list_patient_simulations(
    patient_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Patient not found")

    result = await db.execute(
        select(Simulation)
        .where(
            Simulation.patient_id == patient_id,
            Simulation.clinic_id == current_user.clinic_id,
        )
        .order_by(Simulation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sims = result.scalars().all()

    responses = []
    for sim in sims:
        responses.append(await _get_simulation_response(sim))
    return responses
