const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8002/api/web";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Bağlantı hatası" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// --- Auth ---
export async function login(email: string, password: string) {
  return request<{ access_token: string; user_id: number; email: string }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) }
  );
}

export async function register(email: string, password: string, username?: string) {
  return request<{ access_token: string; user_id: number; email: string }>(
    "/auth/register",
    { method: "POST", body: JSON.stringify({ email, password, username }) }
  );
}

// --- Plans ---
export async function getPlans(params?: { city?: string; limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params?.city) q.set("city", params.city);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return request<{ plans: Plan[]; total: number }>(`/plans?${q}`);
}

export async function getPlan(id: number) {
  return request<VideoDetail>(`/plans/${id}`);
}

export async function getUserPlans(userId: number) {
  return request<{ plans: Plan[]; total: number }>(`/plans/user/${userId}`);
}

export async function getStats() {
  return request<PlatformStats>("/plans/stats");
}

// --- Types ---
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
    route: { optimized_route: { route: any[]; total_distance_km: number } };
    rag: { travel_tips: { tips: any[]; summary: string } };
    ocr_pois: string[] | null;
  } | null;
}

export interface PlatformStats {
  total_videos: number;
  completed_videos: number;
  total_users: number;
  total_cities: number;
}
