"""Admin schemas: users, models, audit, retention, health."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserAdminCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=200)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="viewer", pattern="^(viewer|operator|auditor|admin)$")


class UserAdminUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(viewer|operator|auditor|admin)$")
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_email: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    ip_address: str
    created_at: datetime


class RetentionPolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    resource_type: str = Field(..., pattern="^(media|identity|audit|video)$")
    retention_days: int = Field(..., ge=1, le=3650)
    action: str = Field(default="delete", pattern="^(delete|anonymize)$")
    is_default: bool = False


class RetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    resource_type: str
    retention_days: int
    action: str
    is_default: bool
    created_at: datetime


class ModelStatus(BaseModel):
    name: str
    task: str  # detection | recognition
    provider: str
    embedding_dim: int
    loaded: bool
    is_mock: bool
    path: Optional[str] = None


class HealthComponent(BaseModel):
    name: str
    status: str  # ok | degraded | down
    detail: str = ""


class SystemMetrics(BaseModel):
    total_identities: int
    active_consents: int
    expired_consents: int
    total_media: int
    total_video_jobs: int
    pending_video_jobs: int


class HealthStatus(BaseModel):
    status: str
    version: str
    env: str
    components: list[HealthComponent]
    models: list[ModelStatus]
    metrics: Optional[SystemMetrics] = None
