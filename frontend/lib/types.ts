export type Role = "viewer" | "operator" | "auditor" | "admin";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: Role;
  tenant_id: string;
}

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface QualityReport {
  passed: boolean;
  score: number;
  blur: number;
  lighting: number;
  pose: number;
  face_size_px: number;
  reasons: string[];
}

export interface Detection {
  id: string;
  bbox: BoundingBox;
  confidence: number;
  landmarks: number[][];
  frame_index?: number | null;
  timestamp_ms?: number | null;
  quality?: QualityReport | null;
}

export interface RecognitionCandidate {
  identity_id?: string | null;
  candidate_name?: string | null;
  cosine_similarity: number;
  threshold: number;
  manual_review_required: boolean;
  status: "candidate" | "review_required" | "no_match";
}

export interface DetectionResponse {
  media_id: string;
  kind: string;
  face_count: number;
  processing_ms: number;
  width: number;
  height: number;
  mode: "detection" | "recognition";
  detections: Detection[];
  annotated_url?: string | null;
  recognition?: RecognitionCandidate[] | null;
  notices: string[];
}

export interface MediaRead {
  id: string;
  kind: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  status: string;
  exif_stripped: boolean;
  face_count: number;
  processing_ms: number;
  width: number;
  height: number;
  created_at: string;
  annotated_url?: string | null;
}

export interface VideoJob {
  id: string;
  media_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  sample_fps: number;
  frames_total: number;
  frames_processed: number;
  progress: number;
  faces_detected: number;
  max_faces_in_frame: number;
  duration_seconds: number;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface TimelinePoint {
  timestamp_ms: number;
  face_count: number;
}

export interface VideoReport {
  job: VideoJob;
  media: MediaRead;
  timeline: TimelinePoint[];
  notes: string[];
}

export interface ConsentRead {
  id: string;
  purpose: string;
  granted_at: string;
  expires_at: string;
  retention_until: string;
  revoked_at?: string | null;
  consent_text_version: string;
  evidence_hash: string;
}

export interface EnrollmentRead {
  id: string;
  identity_id: string;
  status: string;
  quality_score: number;
  model_name: string;
  created_at: string;
}

export interface Identity {
  id: string;
  full_name: string;
  notes: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  consent_active: boolean;
  consent_expires_at?: string | null;
  retention_until?: string | null;
  enrollment_count: number;
}

export interface IdentityExport {
  identity: Identity;
  consents: ConsentRead[];
  enrollments: EnrollmentRead[];
  exported_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface AuditLog {
  id: string;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  outcome: string;
  ip_address: string;
  created_at: string;
}

export interface ModelStatus {
  name: string;
  task: "detection" | "recognition";
  provider: string;
  embedding_dim: number;
  loaded: boolean;
  is_mock: boolean;
  path?: string | null;
}

export interface HealthComponent {
  name: string;
  status: "ok" | "degraded" | "down";
  detail: string;
}

export interface SystemMetrics {
  total_identities: number;
  active_consents: number;
  expired_consents: number;
  total_media: number;
  total_video_jobs: number;
  pending_video_jobs: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  env: string;
  components: HealthComponent[];
  models: ModelStatus[];
  metrics?: SystemMetrics | null;
}

export interface RetentionPolicy {
  id: string;
  name: string;
  resource_type: string;
  retention_days: number;
  action: string;
  is_default: boolean;
  created_at: string;
}
