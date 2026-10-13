"""Recognition schemas. Results are always framed as candidates, never identities."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RecognitionCandidate(BaseModel):
    identity_id: Optional[str] = None
    candidate_name: Optional[str] = None
    cosine_similarity: float
    threshold: float
    manual_review_required: bool = True
    status: str = "candidate"  # candidate | review_required | no_match


class RecognitionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    detection_id: Optional[str] = None
    identity_id: Optional[str] = None
    candidate_name: Optional[str] = None
    cosine_similarity: float
    threshold: float
    manual_review_required: bool
    status: str


class RecognizeRequest(BaseModel):
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: int = Field(default=3, ge=1, le=10)
    acknowledge_manual_review: bool = Field(
        default=True,
        description="Caller acknowledges results are advisory and require human review.",
    )
