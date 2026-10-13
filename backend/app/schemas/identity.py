"""Identity, consent and enrollment schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsentInput(BaseModel):
    """Explicit, purpose-bound, expiring consent. All fields are mandatory."""

    consent_granted: bool = Field(
        ..., description="Must be true. The enroller affirms explicit consent was given."
    )
    purpose: str = Field(..., min_length=5, max_length=500)
    expires_at: datetime = Field(..., description="Consent expiry (UTC).")
    retention_until: datetime = Field(..., description="Biometric template purge date (UTC).")
    consent_text_version: str = Field(default="2026-01")

    @field_validator("consent_granted")
    @classmethod
    def _must_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Explicit consent is required before enrollment.")
        return v


class IdentityCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    notes: str = Field(default="", max_length=2000)
    consent: ConsentInput


class IdentityUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ConsentUpdate(BaseModel):
    expires_at: Optional[datetime] = None
    retention_until: Optional[datetime] = None
    purpose: Optional[str] = Field(default=None, min_length=5, max_length=500)
    revoked: Optional[bool] = None


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    purpose: str
    granted_at: datetime
    expires_at: datetime
    retention_until: datetime
    revoked_at: Optional[datetime] = None
    consent_text_version: str
    evidence_hash: str


class QualityReport(BaseModel):
    passed: bool
    score: float
    blur: float
    lighting: float
    pose: float
    face_size_px: int
    reasons: list[str] = []


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    identity_id: str
    status: str
    quality_score: float
    model_name: str
    created_at: datetime


class IdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    notes: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    consent_active: bool = False
    consent_expires_at: Optional[datetime] = None
    retention_until: Optional[datetime] = None
    enrollment_count: int = 0


class IdentityExport(BaseModel):
    """Portable export of a single consented identity (GDPR-style portability)."""

    identity: IdentityRead
    consents: list[ConsentRead]
    enrollments: list[EnrollmentRead]
    exported_at: datetime
