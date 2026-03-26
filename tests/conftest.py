"""
Test fixtures for SmilePreview API tests.

Uses a real async PostgreSQL test database (DATABASE_URL from env).
Mocks external services: Firebase Auth, GCS, Gemini API, Resend email.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.clinic import Clinic
from app.models.consent import ConsentRecord
from app.models.patient import Patient
from app.models.post_procedure import PostProcedureImage
from app.models.share_token import ShareToken
from app.models.simulation import Simulation
from app.models.user import User

# ---------------------------------------------------------------------------
# Use a single event loop for the entire test session
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Database engine & session - created fresh per test function
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_factory


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _setup_database():
    """Create all tables once for the test session, drop them at the end."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    global _engine, _session_factory
    _engine = None
    _session_factory = None


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(_setup_database):
    """Truncate all tables between tests for isolation."""
    yield
    factory = _get_session_factory()
    async with factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a clean database session for direct DB operations in tests."""
    factory = _get_session_factory()
    async with factory() as session:
        yield session


async def _override_get_db():
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# Mock Firebase Auth globally
# ---------------------------------------------------------------------------
_firebase_mock = MagicMock()
_firebase_mock.verify_id_token.return_value = {"uid": "test-firebase-uid"}
_firebase_mock.get_user.return_value = MagicMock(uid="test-firebase-uid")


@pytest.fixture(autouse=True)
def mock_firebase():
    """Mock firebase_admin.auth everywhere so no real Firebase calls are made."""
    # Reset to defaults each test
    _firebase_mock.verify_id_token.return_value = {"uid": "test-firebase-uid"}
    _firebase_mock.verify_id_token.side_effect = None
    _firebase_mock.get_user.return_value = MagicMock(uid="test-firebase-uid")
    _firebase_mock.get_user.side_effect = None

    with (
        patch("app.routers.auth.firebase_auth", _firebase_mock),
        patch("app.dependencies.auth.firebase_auth", _firebase_mock),
    ):
        yield _firebase_mock


# ---------------------------------------------------------------------------
# Mock GCS storage globally
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_storage():
    """Mock all GCS storage functions."""
    with (
        patch(
            "app.services.storage.generate_upload_url",
            return_value=("https://storage.example.com/upload?signed=1", "clinics/test/before/test.jpg"),
        ) as mock_upload_url,
        patch(
            "app.services.storage.generate_download_url",
            return_value="https://storage.example.com/download?signed=1",
        ) as mock_download_url,
        patch(
            "app.services.storage.download_image",
            return_value=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        ) as mock_download,
        patch(
            "app.services.storage.upload_image",
        ) as mock_upload,
        patch("app.routers.simulations.download_image", return_value=b"\xff\xd8\xff\xe0fake-jpeg-bytes"),
        patch("app.routers.simulations.upload_image"),
        patch("app.routers.simulations.generate_download_url", return_value="https://storage.example.com/download?signed=1"),
        patch("app.routers.images.generate_upload_url", return_value=("https://storage.example.com/upload?signed=1", "clinics/test/before/test.jpg")),
        patch("app.routers.images.generate_download_url", return_value="https://storage.example.com/download?signed=1"),
        patch("app.routers.post_procedure.generate_download_url", return_value="https://storage.example.com/download?signed=1"),
        patch("app.routers.share.generate_download_url", return_value="https://storage.example.com/download?signed=1"),
        patch("app.routers.admin.generate_download_url", return_value="https://storage.example.com/download?signed=1"),
    ):
        yield {
            "generate_upload_url": mock_upload_url,
            "generate_download_url": mock_download_url,
            "download_image": mock_download,
            "upload_image": mock_upload,
        }


# ---------------------------------------------------------------------------
# Mock Gemini API
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_gemini():
    """Mock the Gemini generate_smile function."""
    from app.services.gemini import GeminiResult

    successful_result = GeminiResult(
        image_bytes=b"\xff\xd8\xff\xe0generated-smile-bytes",
        error=None,
        elapsed_ms=15000,
        prompt="test prompt",
    )
    with patch(
        "app.routers.simulations.generate_smile",
        new_callable=AsyncMock,
        return_value=successful_result,
    ) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Mock image validation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_image_validator():
    """Mock the dental image validation - defaults to valid."""
    from app.services.image_validator import ValidationResult

    with patch(
        "app.routers.simulations.validate_dental_image",
        new_callable=AsyncMock,
        return_value=ValidationResult(valid=True),
    ) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Mock email service
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_email():
    """Mock the email sending service."""
    with patch("app.services.email.send_share_email", return_value=True) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Mock PDF service
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_pdf():
    """Mock PDF generation."""
    with patch(
        "app.services.pdf.generate_simulation_pdf",
        return_value=b"%PDF-1.4 fake pdf content",
    ) as mock:
        yield mock


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Async HTTP client for testing endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth header helper
# ---------------------------------------------------------------------------
AUTH_HEADER = {"Authorization": "Bearer test-firebase-token"}


def auth_headers(firebase_uid: str = "test-firebase-uid") -> dict:
    """Return auth headers. The mock Firebase will decode any token to the configured UID."""
    return {"Authorization": "Bearer test-firebase-token"}


# ---------------------------------------------------------------------------
# Factory fixtures for creating test data
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def clinic(db_session: AsyncSession) -> Clinic:
    """Create a test clinic with active trial."""
    c = Clinic(
        name="Test Dental Clinic",
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def owner_user(db_session: AsyncSession, clinic: Clinic) -> User:
    """Create an owner user with the test Firebase UID."""
    u = User(
        clinic_id=clinic.id,
        firebase_uid="test-firebase-uid",
        email="owner@testclinic.com",
        name="Dr. Test Owner",
        role="owner",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def provider_user(db_session: AsyncSession, clinic: Clinic) -> User:
    """Create a provider user."""
    u = User(
        clinic_id=clinic.id,
        firebase_uid="provider-firebase-uid",
        email="provider@testclinic.com",
        name="Dr. Provider",
        role="provider",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def nurse_user(db_session: AsyncSession, clinic: Clinic) -> User:
    """Create a nurse user."""
    u = User(
        clinic_id=clinic.id,
        firebase_uid="nurse-firebase-uid",
        email="nurse@testclinic.com",
        name="Nurse Test",
        role="nurse",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def platform_admin(db_session: AsyncSession, clinic: Clinic) -> User:
    """Create a platform admin user with the test Firebase UID."""
    u = User(
        clinic_id=clinic.id,
        firebase_uid="test-firebase-uid",
        email="admin@smilepreview.com",
        name="Platform Admin",
        role="owner",
        is_platform_admin=True,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def other_clinic(db_session: AsyncSession) -> Clinic:
    """Create a second clinic for cross-clinic isolation tests."""
    c = Clinic(
        name="Other Dental Clinic",
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def other_clinic_user(db_session: AsyncSession, other_clinic: Clinic) -> User:
    """Create a user belonging to the other clinic."""
    u = User(
        clinic_id=other_clinic.id,
        firebase_uid="other-clinic-firebase-uid",
        email="other@otherclinic.com",
        name="Dr. Other",
        role="owner",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def patient(db_session: AsyncSession, clinic: Clinic) -> Patient:
    """Create a test patient."""
    p = Patient(
        clinic_id=clinic.id,
        display_name="John D.",
        external_id="PAT-001",
        email="john@example.com",
        phone="+15125551234",
        notes="Test patient",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def other_clinic_patient(db_session: AsyncSession, other_clinic: Clinic) -> Patient:
    """Create a patient in the other clinic."""
    p = Patient(
        clinic_id=other_clinic.id,
        display_name="Jane O.",
        external_id="PAT-OTHER",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def completed_simulation(
    db_session: AsyncSession, clinic: Clinic, patient: Patient, owner_user: User
) -> Simulation:
    """Create a completed simulation with result image."""
    s = Simulation(
        clinic_id=clinic.id,
        patient_id=patient.id,
        created_by=owner_user.id,
        treatment_type="veneers",
        shade="natural",
        before_image_key=f"clinics/{clinic.id}/before/test.jpg",
        result_image_key=f"clinics/{clinic.id}/results/test.jpg",
        status="completed",
        generation_time_ms=18000,
        prompt_used="test prompt",
        model_version="gemini-3.1-flash-image-preview",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def failed_simulation(
    db_session: AsyncSession, clinic: Clinic, patient: Patient, owner_user: User
) -> Simulation:
    """Create a failed simulation."""
    s = Simulation(
        clinic_id=clinic.id,
        patient_id=patient.id,
        created_by=owner_user.id,
        treatment_type="whitening",
        shade="hollywood",
        before_image_key=f"clinics/{clinic.id}/before/test2.jpg",
        status="failed",
        error_message="Image could not be processed.",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def share_token(
    db_session: AsyncSession, completed_simulation: Simulation, owner_user: User
) -> ShareToken:
    """Create a valid share token."""
    st = ShareToken(
        simulation_id=completed_simulation.id,
        token="valid-test-token-abc123",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=owner_user.id,
    )
    db_session.add(st)
    await db_session.commit()
    await db_session.refresh(st)
    return st


@pytest_asyncio.fixture
async def expired_share_token(
    db_session: AsyncSession, completed_simulation: Simulation, owner_user: User
) -> ShareToken:
    """Create an expired share token."""
    st = ShareToken(
        simulation_id=completed_simulation.id,
        token="expired-test-token-xyz789",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        created_by=owner_user.id,
    )
    db_session.add(st)
    await db_session.commit()
    await db_session.refresh(st)
    return st
