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
 * Aynı anda devam eden TEK bir refresh çağrısı — `refreshAccessToken()`'ın
 * birden fazla eşzamanlı çağırıcısı (ör. bir sayfanın `Promise.all` ile
 * paralel ateşlediği iki authenticated istek, ikisi de aynı anda 401
 * alırsa — bkz. `app/trips/[id]/optimize/page.tsx`'in `Promise.all([...])`'ı)
 * AYNI Task'ı paylaşır, HER BİRİ KENDİ `/auth/refresh` isteğini ateşlemez.
 * Bu olmadan: iki eşzamanlı çağrı aynı (henüz rotate edilmemiş) refresh
 * token'ı okur, biri başarıyla yeni bir çift kalıcı hale getirir, diğeri
 * ise artık geçersiz olan AYNI eski token'ı kullanmaya çalışıp reddedilir
 * — ve o reddedilme koşulsuzca `clearAuthStorage()` çağırıp BİRAZ ÖNCE
 * başarıyla yenilenmiş GEÇERLİ oturumu siler, kullanıcıyı gereksiz yere
 * `/login`'e yönlendirir (M38 audit bulgusu — iOS'un `AuthEnvironment.
 * inFlightRefresh`'iyle AYNI kök neden/düzeltme, core-api'nin
 * `REFRESH_TOKEN_RACE_LOST` kodu tam da bu senaryoyu öngörüyor).
 */
let inFlightRefresh: Promise<string | null> | null = null;

/**
 * Access token süresi dolduğunda (401) çağrılır. Başarılıysa yeni token
 * çiftini kaydeder ve yeni access token'ı döner; başarısızsa storage'ı
 * temizler ve null döner. Recursive 401 handling'e girmemek için ham
 * `fetch` kullanır (request() üzerinden gitmez).
 */
async function refreshAccessToken(): Promise<string | null> {
  if (inFlightRefresh) return inFlightRefresh;

  inFlightRefresh = performRefresh();
  try {
    return await inFlightRefresh;
  } finally {
    inFlightRefresh = null;
  }
}

async function performRefresh(): Promise<string | null> {
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
    409: "Bu işlem artık geçerli değil — sayfa güncel olmayabilir.",
    413: "Dosya çok büyük.",
    422: "Gönderilen veriler hatalı.",
    429: "Çok fazla istek gönderildi. Lütfen bekleyin.",
    500: "Sunucu hatası. Lütfen daha sonra tekrar deneyin.",
    503: "Servis geçici olarak kullanılamıyor.",
    504: "Sunucu zaman aşımına uğradı.",
  };
  return HTTP_MESSAGES[status] ?? `Bir hata oluştu (HTTP ${status}).`;
}

/**
 * Yanıt gövdesinden makine-okunabilir hata kodunu (core-api'nin kendi
 * `code` alanı, ör. "STALE_UNDO"/"ITINERARY_NOT_FOUND") çıkarır — `Error.message`
 * yalnızca İNSAN-okunabilir metni taşıdığından, bir çağıranın belirli bir
 * hatayı (ör. STALE_UNDO'yu "sayfayı yenile" davranışıyla) TÜRKÇE METNİ
 * eşleştirerek değil, bu koddan ayırt edebilmesi için (bkz. ApiError altında).
 */
function extractErrorCode(body: unknown): string | undefined {
  if (body && typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.code === "string") return obj.code;
    if (obj.error && typeof obj.error === "object") {
      const err = obj.error as Record<string, unknown>;
      if (typeof err.code === "string") return err.code;
    }
  }
  return undefined;
}

/**
 * `Error`'ın, sunucunun makine-okunabilir `code`'unu VE HTTP durumunu da
 * taşıyan genişletilmiş biçimi — yalnızca belirli bir hata koduna göre dallanma
 * GEREKEN çağıranlar (bkz. Apply History → `STALE_UNDO` işleme) bunu
 * `instanceof ApiError` ile kontrol eder; geri kalan her yer zaten olduğu
 * gibi `error.message`i kullanmaya devam eder.
 */
export class ApiError extends Error {
  readonly code?: string;
  readonly status: number;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
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
        // Geçerli sayfayı `next` olarak taşı — aksi halde oturum süresi
        // dolan bir kullanıcı /login'e düşer ve giriş yaptıktan sonra
        // /dashboard'a atılır, bulunduğu sayfaya DEĞİL (M34 audit bulgusu).
        const current = window.location.pathname + window.location.search;
        const target = current && current !== "/" ? `/login?next=${encodeURIComponent(current)}` : "/login";
        window.location.href = target;
      }
    }

    const body = await res.json().catch(() => null);
    throw new ApiError(extractErrorMessage(body, res.status), res.status, extractErrorCode(body));
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
  const result = await request<AuthTokens>(
    "/auth/register",
    { method: "POST", body: JSON.stringify({ email, password, username }) }
  );
  trackReferralJoinIfPresent();
  return result;
}

/**
 * Şifre sıfırlama e-postası ister. Backend, hesap var/yok fark etmeksizin
 * AYNI genel yanıtı döner (kullanıcı numaralandırmayı önlemek için) — bu
 * yüzden burada da başarı/hata ayrımı YAPILMAZ, çağıran her zaman aynı
 * genel mesajı gösterir.
 */
export async function forgotPassword(email: string): Promise<void> {
  await request<{ status: string }>(
    "/auth/forgot-password",
    { method: "POST", body: JSON.stringify({ email }) }
  );
}

/**
 * Sıfırlama token'ını yeni şifreyle değiştirir. Başarısızsa (geçersiz/
 * süresi dolmuş/kullanılmış token) ApiError fırlatır — çağıran `code`
 * alanına göre değil, `message`i doğrudan gösterir (backend zaten Türkçe
 * kullanıcı-dostu mesaj döner).
 */
export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await request<{ status: string }>(
    "/auth/reset-password",
    { method: "POST", body: JSON.stringify({ token, new_password: newPassword }) }
  );
}

/**
 * Google OAuth Authorization Code'unu (callback sayfasında alınan `code`)
 * core-api'ye ileterek giriş/hesap oluşturma/hesap bağlama işlemini
 * tamamlar. `redirectUri`, Google'a başlangıçta gönderilenle BİREBİR aynı
 * olmalı (OAuth spec gereği) — core-api ayrıca kendi allowlist'ine göre
 * ayrıca doğrular.
 */
export async function googleSignIn(code: string, redirectUri: string): Promise<AuthTokens> {
  return request<AuthTokens>(
    "/auth/google",
    { method: "POST", body: JSON.stringify({ code, redirect_uri: redirectUri }) }
  );
}

// ─── Analytics ─────────────────────────────────────────────────────────────
//
// Shared-trip büyüme hunisi (bkz. docs/analytics/shared-trip-events.md).

/**
 * Bir event'i ateşler. Kasıtlı olarak request() ÜZERİNDEN GİTMEZ: request()'in
 * 401 → refresh → /login yönlendirme mantığı bir analytics çağrısı için asla
 * tetiklenmemeli — best-effort bir arka plan isteği kullanıcıyı /login'e
 * göndermemeli. logout()/refreshAccessToken() ile aynı gerekçeyle ham fetch
 * kullanılıyor (bkz. yukarısı).
 */
export function trackAnalyticsEvent(
  event: string,
  tripId: number,
  source?: string,
  metadata?: Record<string, unknown>,
): void {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  fetch(`${BASE_URL}/analytics/events`, {
    method: "POST",
    headers,
    body: JSON.stringify({ event, trip_id: tripId, source, metadata }),
  }).catch(() => { /* best-effort — analytics hiçbir zaman kullanıcı deneyimini etkilemez */ });
}

const REFERRAL_STORAGE_KEY = "tripclip_referral";
const REFERRAL_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 gün — bu süreden eski bir ziyaret artık ilişkilendirilmez

interface ReferralMarker {
  tripId: number;
  ts: number;
}

/**
 * Bir paylaşım sayfası ziyaretini işaretler — kullanıcı sonradan kayıt olursa
 * `shared_trip_joined` bu ziyaretle ilişkilendirilebilsin diye (bkz.
 * trackReferralJoinIfPresent, register() içinde çağrılır).
 */
export function markShareReferral(tripId: number): void {
  if (typeof window === "undefined") return;
  try {
    const marker: ReferralMarker = { tripId, ts: Date.now() };
    localStorage.setItem(REFERRAL_STORAGE_KEY, JSON.stringify(marker));
  } catch { /* localStorage kullanılamıyor olabilir (gizli sekme vb.) — sessizce vazgeç */ }
}

function trackReferralJoinIfPresent(): void {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(REFERRAL_STORAGE_KEY);
    if (!raw) return;
    localStorage.removeItem(REFERRAL_STORAGE_KEY);

    const marker: ReferralMarker = JSON.parse(raw);
    if (Date.now() - marker.ts > REFERRAL_TTL_MS) return;
    trackAnalyticsEvent("shared_trip_joined", marker.tripId, "share_page_referral");
  } catch { /* bozuk/eksik veri — sessizce vazgeç */ }
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

// ─── Trip sharing ──────────────────────────────────────────────────────────
//
// Web'in rolü yalnızca davet ALAN taraf: önizleme (anonim) + kabul/reddet
// (giriş gerektirir). Davet OLUŞTURMA/collaborator yönetimi iOS'ta — bkz.
// services/web-bff/app/routes/trip_sharing.py.

export async function getSharePreview(token: string) {
  return request<SharePreview>(`/shares/${token}/preview`);
}

export async function acceptShare(token: string) {
  return request<AcceptShareResult>("/shares/accept", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function declineShare(token: string) {
  return request<{ success: boolean }>("/shares/decline", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export interface SharePreview {
  trip_title: string;
  stops_count: number;
  role: string;
}

export interface AcceptShareResult {
  trip_id: number;
}

// ─── Trip Builder (Milestone 21 — Web AI Trip Optimizer) ───────────────────
//
// Bilerek MİNİMAL: yalnızca okuma (list/detail) — trip OLUŞTURMA/durak
// düzenleme/silme burada YOK, iOS'a özel kalmaya devam ediyor (bkz.
// services/web-bff/app/routes/trips.py'nin kendi doc yorumu,
// docs/ios-trip-optimizer.md "Web AI Trip Optimizer"). Alan adları
// core-api'nin TripDetailResponse/TripStopDTO'suyla birebir aynı (web-bff
// burada hiçbir dönüşüm yapmıyor, ham JSON'u olduğu gibi iletiyor).

export interface TripStop {
  place_id: number;
  name: string;
  lat: number;
  lng: number;
  city: string | null;
  category: string | null;
  day_index: number;
  order_index: number;
}

export interface TripSummary {
  id: number;
  title: string;
  total_distance_km: number | null;
  created_at: string | null;
  stops_count: number;
  role: string;
}

export interface TripDetail {
  id: number;
  title: string;
  total_distance_km: number | null;
  created_at: string | null;
  days: TripStop[][];
  stops_count: number;
  owner_id: number;
  /** 'owner' | 'editor' | 'viewer' — yalnızca UI ipucu, sunucu her isteği ayrıca doğrular. */
  your_role: string;
  applied_itinerary_id: number | null;
  itinerary_applied_at: string | null;
}

export async function getTrips() {
  return request<{ trips: TripSummary[] }>("/trips");
}

export async function getTrip(id: number) {
  return request<TripDetail>(`/trips/${id}`);
}

/** Trip'in kendi TÜM duraklarının (day'lerden bağımsız, tekilleştirilmiş) düz listesi. */
export function flattenTripStops(trip: TripDetail): TripStop[] {
  return trip.days.flat();
}

// ─── AI Trip Optimizer (Milestone 21) ───────────────────────────────────────
//
// core-api'nin OptimizeTripRequest/OptimizeTripResponse'uyla birebir eşleşir
// (bkz. docs/trip-optimizer.md "API") — burada hiçbir optimizasyon mantığı
// YOK, yalnızca Web BFF'i (zaten var olan) proxy'liyoruz.

export type TransportMode = "automobile" | "walking" | "transit";

export interface OptimizeTripRequest {
  selected_place_ids: number[];
  start_date?: string | null;
  duration_days?: number | null;
  preferred_start_time?: string;
  preferred_end_time?: string;
  strategy?: string;
}

export interface ItineraryStop {
  place_id: number | null;
  name: string;
  lat: number | null;
  lng: number | null;
  day_index: number;
  order_index: number;
  arrival_time: string | null;
  departure_time: string | null;
  visit_duration_minutes: number;
  travel_time_to_next_minutes: number | null;
  travel_distance_to_next_km: number | null;
}

export interface ItineraryDay {
  day_index: number;
  date: string | null;
  stops: ItineraryStop[];
}

export interface Itinerary {
  id: number;
  trip_id: number;
  strategy_name: string;
  optimization_score: number;
  total_distance_km: number;
  total_travel_time_minutes: number;
  warnings: string[];
  created_at: string | null;
  days: ItineraryDay[];
}

export interface ItinerarySummary {
  id: number;
  trip_id: number;
  strategy_name: string;
  optimization_score: number;
  total_distance_km: number;
  total_travel_time_minutes: number;
  warnings: string[];
  created_at: string | null;
  days_count: number;
  stops_count: number;
}

export interface AppliedTripStop {
  place_id: number;
  name: string;
  lat: number;
  lng: number;
  city: string | null;
  category: string | null;
  day_index: number;
  order_index: number;
}

export interface ApplyResult {
  trip_id: number;
  itinerary_id: number;
  stops: AppliedTripStop[];
  stops_count: number;
  applied_at: string;
}

export async function optimizeTrip(tripId: number, body: OptimizeTripRequest) {
  return request<Itinerary>(`/trips/${tripId}/optimize`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getItineraries(tripId: number) {
  return request<{ itineraries: ItinerarySummary[] }>(`/trips/${tripId}/itineraries`);
}

export async function getItinerary(id: number) {
  return request<Itinerary>(`/itineraries/${id}`);
}

export async function applyItinerary(id: number) {
  return request<ApplyResult>(`/itineraries/${id}/apply`, { method: "POST" });
}

export async function deleteItinerary(id: number) {
  return request<{ success: boolean }>(`/itineraries/${id}`, { method: "DELETE" });
}

// ─── Apply History & Undo (Milestone 21) ────────────────────────────────────

export interface ApplyHistoryEntry {
  id: number;
  itinerary_id: number | null;
  itinerary_created_at: string | null;
  is_undo: boolean;
  applied_at: string;
  actor_user_id: number;
  is_undoable: boolean;
}

export interface UndoResult {
  trip_id: number;
  history_id: number;
  itinerary_id: number | null;
  stops: AppliedTripStop[];
  stops_count: number;
  applied_at: string;
}

export async function getApplyHistory(tripId: number) {
  return request<{ entries: ApplyHistoryEntry[] }>(`/trips/${tripId}/itinerary-apply-history`);
}

export async function undoApply(tripId: number, historyId: number) {
  return request<UndoResult>(`/trips/${tripId}/itinerary-apply-history/${historyId}/undo`, {
    method: "POST",
  });
}

// ─── Trip Assistant (Milestone 26) ──────────────────────────────────────────
//
// core-api'nin AssistantRequestDTO/AssistantResponseDTO'suyla birebir eşleşir
// (bkz. docs/trip-assistant.md "API contract") — burada hiçbir AI/context
// mantığı YOK, yalnızca Web BFF'i (zaten var olan) proxy'liyoruz. Salt-okunur:
// hiçbir trip/itinerary state'ini DEĞİŞTİRMEZ.

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantReference {
  type: "stop";
  day_index: number;
  place_id: number;
}

export interface AssistantRequest {
  message: string;
  history?: AssistantMessage[];
}

export interface AssistantResponse {
  answer: string;
  references: AssistantReference[];
}

export async function askTripAssistant(tripId: number, body: AssistantRequest) {
  return request<AssistantResponse>(`/trips/${tripId}/assistant`, {
    method: "POST",
    body: JSON.stringify(body),
  });
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
