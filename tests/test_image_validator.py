"""Tests for image validation service and simulation integration."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.user import User
from app.services.image_validator import ValidationResult, validate_dental_image
from tests.conftest import AUTH_HEADER


# ---------------------------------------------------------------------------
# Unit tests for validate_dental_image
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_valid_image():
    """Valid face+teeth image should pass validation."""
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps({"valid": True, "reason": "Face with visible teeth detected"})}]
                }
            }
        ]
    }

    with patch("app.services.image_validator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post.return_value = mock_response_obj

        result = await validate_dental_image(b"fake-image-bytes")
        assert result.valid is True


@pytest.mark.asyncio
async def test_validate_no_face():
    """Image without a face should fail validation."""
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {"valid": False, "reason": "No human face is present in this image."}
                            )
                        }
                    ]
                }
            }
        ]
    }

    with patch("app.services.image_validator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post.return_value = mock_response_obj

        result = await validate_dental_image(b"fake-image-bytes")
        assert result.valid is False
        assert "face" in result.reason.lower()


@pytest.mark.asyncio
async def test_validate_api_timeout_allows_through():
    """If validation API times out, image should be allowed through."""
    import httpx as real_httpx

    with patch("app.services.image_validator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = real_httpx.TimeoutException("timeout")

        result = await validate_dental_image(b"fake-image-bytes")
        assert result.valid is True


@pytest.mark.asyncio
async def test_validate_api_error_allows_through():
    """If validation API returns error, image should be allowed through."""
    with patch("app.services.image_validator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 500
        mock_client.post.return_value = mock_response_obj

        result = await validate_dental_image(b"fake-image-bytes")
        assert result.valid is True


@pytest.mark.asyncio
async def test_validate_malformed_response_allows_through():
    """If validation response is unparseable, image should be allowed through."""
    mock_response = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}

    with patch("app.services.image_validator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.post.return_value = mock_response_obj

        result = await validate_dental_image(b"fake-image-bytes")
        assert result.valid is True


# ---------------------------------------------------------------------------
# Integration tests - validation rejection flows through simulation endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_simulation_rejected_by_validation(
    client: AsyncClient,
    owner_user: User,
    patient: Patient,
    clinic: Clinic,
    mock_image_validator,
    mock_gemini,
):
    """Simulation should fail when image validation rejects the photo."""
    mock_image_validator.return_value = ValidationResult(
        valid=False,
        reason="No human face is present in this image.",
    )

    before_key = f"clinics/{clinic.id}/before/landscape.jpg"
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": before_key,
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert "face" in data["error_message"].lower()

    # Gemini should NOT have been called
    mock_gemini.assert_not_called()


@pytest.mark.asyncio
async def test_create_simulation_validation_passes(
    client: AsyncClient,
    owner_user: User,
    patient: Patient,
    clinic: Clinic,
    mock_image_validator,
    mock_gemini,
):
    """Simulation should proceed when image validation passes."""
    mock_image_validator.return_value = ValidationResult(valid=True)

    before_key = f"clinics/{clinic.id}/before/face.jpg"
    resp = await client.post(
        "/simulations",
        headers=AUTH_HEADER,
        json={
            "patient_id": str(patient.id),
            "before_image_key": before_key,
            "treatment_type": "veneers",
            "shade": "natural",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"

    # Gemini SHOULD have been called
    mock_gemini.assert_called_once()
