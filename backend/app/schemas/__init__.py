"""Pydantic v2 schemas (request/response contracts)."""
from app.schemas.admin import (  # noqa: F401
    AuditLogRead,
    HealthComponent,
    HealthStatus,
    ModelStatus,
    RetentionPolicyCreate,
    RetentionPolicyRead,
    SystemMetrics,
    UserAdminCreate,
    UserAdminRead,
    UserAdminUpdate,
)
from app.schemas.auth import (  # noqa: F401
    LoginRequest,
    TokenResponse,
    UserRead,
)
from app.schemas.common import ErrorResponse, MessageResponse, Page  # noqa: F401
from app.schemas.identity import (  # noqa: F401
    ConsentInput,
    ConsentRead,
    EnrollmentRead,
    IdentityCreate,
    IdentityRead,
    IdentityUpdate,
    QualityReport,
)
from app.schemas.media import (  # noqa: F401
    BoundingBox,
    DetectionRead,
    DetectionResponse,
    MediaRead,
    TimelinePoint,
    VideoJobRead,
    VideoReport,
)
from app.schemas.recognition import (  # noqa: F401
    RecognitionCandidate,
    RecognitionResultRead,
)

__all__ = [name for name in dir() if not name.startswith("_")]
