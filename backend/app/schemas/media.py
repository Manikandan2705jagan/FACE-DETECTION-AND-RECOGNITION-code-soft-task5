"""Media / detection / video schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)


class DetectionRead(BaseModel):
    id: str
    bbox: BoundingBox
    confidence: float
    landmarks: list[list[float]] = []
    frame_index: Optional[int] = None
    timestamp_ms: Optional[int] = None
    quality: Optional[dict] = None


class DetectionResponse(BaseModel):
    media_id: str
    kind: str
    face_count: int
    processing_ms: float
    width: int
    height: int
    mode: str  # detection | recognition
    detections: list[DetectionRead]
    annotated_url: Optional[str] = None
    recognition: Optional[list["RecognitionCandidate"]] = None
    notices: list[str] = []


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: str
    exif_stripped: bool
    face_count: int
    processing_ms: float
    width: int
    height: int
    created_at: datetime
    annotated_url: Optional[str] = None


class TimelinePoint(BaseModel):
    timestamp_ms: int
    face_count: int


class VideoJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_id: str
    status: str
    sample_fps: float
    frames_total: int
    frames_processed: int
    progress: float
    faces_detected: int
    max_faces_in_frame: int
    duration_seconds: float
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class VideoReport(BaseModel):
    job: VideoJobRead
    media: MediaRead
    timeline: list[TimelinePoint]
    notes: list[str] = []


from app.schemas.recognition import RecognitionCandidate  # noqa: E402

DetectionResponse.model_rebuild()
