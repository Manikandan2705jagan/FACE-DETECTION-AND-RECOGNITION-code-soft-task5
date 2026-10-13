import type {
  AuditLog,
  DetectionResponse,
  HealthStatus,
  Identity,
  IdentityExport,
  MediaRead,
  ModelStatus,
  Page,
  RetentionPolicy,
  SystemMetrics,
  TokenResponse,
  User,
  VideoJob,
  VideoReport,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

const TOKEN_KEY = "jarvas_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  auth?: boolean;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = new URL(`${API_BASE}/api/v1${path}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, formData, auth = true, query } = options;
  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let payload: BodyInit | undefined;
  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), { method, headers, body: payload });
  } catch (err) {
    throw new ApiError(
      "Cannot reach the JARVAS API. Is the backend running?",
      0,
    );
  }

  if (response.status === 401 && auth) {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      (isJson && (data?.detail?.message || data?.detail)) ||
      (typeof data === "string" ? data : "Request failed");
    const message = Array.isArray(detail)
      ? detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ")
      : typeof detail === "object"
        ? JSON.stringify(detail)
        : String(detail);
    throw new ApiError(message, response.status);
  }

  return data as T;
}

/* ----------------------------- Auth ------------------------------------- */
export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/token", { method: "POST", body: { email, password }, auth: false }),

  me: () => request<User>("/auth/me"),

  /* --------------------------- Images ---------------------------------- */
  detect: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<DetectionResponse>("/images/detect", { method: "POST", formData: fd });
  },

  recognize: (file: File, threshold?: number, topK = 3) => {
    const fd = new FormData();
    fd.append("file", file);
    if (threshold !== undefined) fd.append("threshold", String(threshold));
    fd.append("top_k", String(topK));
    return request<DetectionResponse>("/images/recognize", { method: "POST", formData: fd });
  },

  listMedia: () => request<MediaRead[]>("/images"),

  getMedia: (id: string) => request<MediaRead>(`/images/${id}`),

  annotatedUrl: (id: string) => `${API_BASE}/api/v1/images/${id}/annotated`,

  /* --------------------------- Videos ---------------------------------- */
  uploadVideo: (file: File, sampleFps: number, processAsync = false) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("sample_fps", String(sampleFps));
    fd.append("process_async", String(processAsync));
    return request<VideoJob>("/videos", { method: "POST", formData: fd });
  },

  listVideoJobs: () => request<VideoJob[]>("/videos"),
  getVideoJob: (id: string) => request<VideoJob>(`/videos/${id}`),
  getVideoReport: (id: string) => request<VideoReport>(`/videos/${id}/report`),
  videoReportUrl: (id: string) => `${API_BASE}/api/v1/videos/${id}/report.json`,

  /* --------------------------- Gallery --------------------------------- */
  galleryNotices: () =>
    request<{ enrollment: string; recognition: string; general: string }>("/gallery/notices", {
      auth: false,
    }),

  listIdentities: (params: { q?: string; consent_status?: string; page?: number; size?: number } = {}) =>
    request<Page<Identity>>("/gallery/identities", { query: params }),

  createIdentity: (payload: {
    full_name: string;
    notes: string;
    consent: {
      consent_granted: boolean;
      purpose: string;
      expires_at: string;
      retention_until: string;
      consent_text_version: string;
    };
  }) => request<Identity>("/gallery/identities", { method: "POST", body: payload }),

  updateIdentity: (id: string, payload: { full_name?: string; notes?: string }) =>
    request<Identity>(`/gallery/identities/${id}`, { method: "PATCH", body: payload }),

  updateConsent: (
    id: string,
    payload: { expires_at?: string; retention_until?: string; purpose?: string; revoked?: boolean },
  ) => request<Identity>(`/gallery/identities/${id}/consent`, { method: "PATCH", body: payload }),

  enroll: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ id: string; quality_score: number; status: string }>(
      `/gallery/identities/${id}/enroll`,
      { method: "POST", formData: fd },
    );
  },

  exportIdentity: (id: string) => request<IdentityExport>(`/gallery/identities/${id}/export`),
  deleteIdentity: (id: string) =>
    request<void>(`/gallery/identities/${id}`, { method: "DELETE" }),

  /* ---------------------------- Admin ---------------------------------- */
  health: () => request<HealthStatus>("/health", { auth: false }),
  healthMetrics: () => request<HealthStatus>("/health/metrics"),
  models: () => request<ModelStatus[]>("/admin/models"),
  metrics: () => request<SystemMetrics>("/admin/metrics"),

  listUsers: () => request<User[]>("/admin/users"),
  createUser: (payload: { email: string; full_name: string; password: string; role: string }) =>
    request<User>("/admin/users", { method: "POST", body: payload }),
  updateUser: (id: string, payload: { full_name?: string; role?: string; is_active?: boolean; password?: string }) =>
    request<User>(`/admin/users/${id}`, { method: "PATCH", body: payload }),

  audit: (params: { action?: string; page?: number; size?: number } = {}) =>
    request<Page<AuditLog>>("/admin/audit", { query: params }),

  listRetention: () => request<RetentionPolicy[]>("/admin/retention"),
  createRetention: (payload: {
    name: string;
    resource_type: string;
    retention_days: number;
    action: string;
    is_default: boolean;
  }) => request<RetentionPolicy>("/admin/retention", { method: "POST", body: payload }),
  deleteRetention: (id: string) =>
    request<void>(`/admin/retention/${id}`, { method: "DELETE" }),
  runRetention: () => request<{ biometrics: unknown; media: unknown }>("/admin/retention/run", { method: "POST" }),

  adminVideoJobs: () => request<VideoJob[]>("/admin/video-jobs"),
};

export { API_BASE };
