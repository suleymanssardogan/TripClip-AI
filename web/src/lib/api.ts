const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8002/api/web";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

function clearAuthStorage(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user_id");
  localStorage.removeItem("email");
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  user_id: number;
  email: string;
}

/**
 * Login/register yanıtından gelen token çiftini localStorage'a yazar.
 * Tekrarlanan localStorage.setItem üçlüsü yerine tek bir yer.
 */
export function saveAuthTokens(data: AuthTokens): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  localStorage.setItem("user_id", String(data.user_id));
  localStorage.setItem("email", data.email);
}

/**
 * Sunucu tarafında refresh token'ı iptal etmeyi dener (best-effort), sonra
 * local storage'ı temizleyip /login'e yönlendirir.
 */
export function logout(): void {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => { /* best-effort — client tarafı temizlik yine de yapılır */ });
  }
  clearAuthStorage();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

/**
 * Access token süresi dolduğunda (401) çağrılır. Başarılıysa yeni token
 * çiftini kaydeder ve yeni access token'ı döner; başarısızsa storage'ı
 * temizler ve null döner. Recursive 401 handling'e girmemek için ham
 * `fetch` kullanır (request() üzerinden gitmez).
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      clearAuthStorage();
      return null;
    }
    const data: AuthTokens = await res.json();
    saveAuthTokens(data);
    return data.access_token;
  } catch {
    return null;
  }
}

/**
 * Hata yanıtından kullanıcı dostu mesaj çıkar.
 */
function extractErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (obj.error && typeof obj.error === "object") {
      const err = obj.error as Record<string, unknown>;
      if (typeof err.message === "string") return err.message;
    }
    if (typeof obj.detail === "string") return obj.detail;
    if (typeof obj.message === "string") return obj.message;
  }

  const HTTP_MESSAGES: Record<number, string> = {
    400: "Geçersiz istek.",
    401: "Oturum sona erdi. Lütfen tekrar giriş yapın.",
    403: "Bu işlem için yetkiniz yok.",
    404: "Kaynak bulunamadı.",
    413: "Dosya çok büyük.",
    422: "Gönderilen veriler hatalı.",
    429: "Çok fazla istek gönderildi. Lütfen bekleyin.",
    500: "Sunucu hatası. Lütfen daha sonra tekrar deneyin.",
    503: "Servis geçici olarak kullanılamıyor.",
    504: "Sunucu zaman aşımına uğradı.",
  };
  return HTTP_MESSAGES[status] ?? `Bir hata oluştu (HTTP ${status}).`;
}

async function request<T>(path: string, options: RequestInit = {}, _retried = false): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error("Sunucuya ulaşılamıyor. İnternet bağlantınızı veya servis durumunu kontrol edin.");
  }

  if (!res.ok) {
    // Token expiry: try a silent refresh once, then retry the original request.
    // Auth endpoints (/auth/*) return 401 for wrong credentials — never refresh those.
    if (res.status === 401 && token && !_retried && !path.startsWith("/auth")) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return request<T>(path, options, true);
      }
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }

    const body = await res.json().catch(() => null);
    throw new Error(extractErrorMessage(body, res.status));
  }

  return res.json();
}

// ─── Auth ──────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  return request<AuthTokens>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) }
  );
}

export async function register(email: string, password: string, username?: string) {
  return request<AuthTokens>(
    "/auth/register",
    { method: "POST", body: JSON.stringify({ email, password, username }) }
  );
}

// ─── Videos ────────────────────────────────────────────────────────────────

export interface ProgressResponse {
  stage: string;
  percent: number;
}

export async function getVideoProgress(id: number): Promise<ProgressResponse> {
  return request<ProgressResponse>(`/videos/${id}/progress`);
}

// ─── Plans ─────────────────────────────────────────────────────────────────

export async function getPlans(params?: { city?: string; limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params?.city)   q.set("city",   params.city);
  if (params?.limit)  q.set("limit",  String(params.limit));
  if (params?.offset !== undefined) q.set("offset", String(params.offset));
  return request<{ plans: Plan[]; total: number }>(`/plans?${q}`);
}

export async function getPlan(id: number) {
  return request<VideoDetail>(`/plans/${id}`);
}

/** Editor'de sürükle-bırak ile belirlenen durak sırasını kalıcı olarak kaydeder (gün başına ID listesi). */
export async function updatePlanOrder(id: number, order: number[][]) {
  return request<{ success: boolean }>(`/plans/${id}/order`, {
    method: "PATCH",
    body: JSON.stringify({ order }),
  });
}

export async function getUserPlans(userId: number) {
  return request<{ plans: Plan[]; total: number }>(`/plans/user/${userId}`);
}

export async function getStats() {
  return request<PlatformStats>("/plans/stats");
}

// ─── Tipler ────────────────────────────────────────────────────────────────

export interface Plan {
  id: number;
  filename: string;
  status: string;
  duration: number | null;
  created_at: string;
  locations_count: number;
  top_location: string | null;
  ocr_preview: string[];
  processing_time: number | null;
}

export interface VideoDetail {
  id: number;
  filename: string;
  status: string;
  duration: number | null;
  created_at: string;
  ai_results: {
    processing_time: number;
    detections: { count: number };
    ocr: { extracted_texts: string[] };
    audio: { transcription: { transcript: string; language: string } };
    ner: { extracted_locations: string[] };
    nominatim: {
      deduplicated_locations: Array<{
        original_name: string;
        place_data: {
          name: string;
          location: { lat: number; lng: number };
          type: string;
        };
      }>;
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    route: { optimized_route: { route: any[]; total_distance_km: number } };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rag: { travel_tips: { tips: any[]; summary: string } };
    ocr_pois: string[] | null;
  } | null;
  degradation: {
    total_services: number;
    successful: number;
    failed_services: string[];
  } | null;
  stop_order: number[][] | null;
}

export interface PlatformStats {
  total_videos: number;
  completed_videos: number;
  total_users: number;
  total_cities: number;
}
