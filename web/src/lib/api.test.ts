import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getTrips } from "./api";

/**
 * `api.ts`'in kendisi (özellikle `request()`/`refreshAccessToken()`)
 * daha önce hiç doğrudan test edilmemişti — sayfa testleri her zaman
 * `@/lib/api`'yi TAMAMEN mock'layıp bu iç mantığı hiç çalıştırmıyordu.
 * M38 audit bulgusu: iki eşzamanlı authenticated istek aynı anda 401
 * alırsa (ör. `app/trips/[id]/optimize/page.tsx`'in `Promise.all([...])`'ı),
 * her biri KENDİ `/auth/refresh` isteğini bağımsız ateşliyordu — biri
 * başarıyla yeni bir token çifti kaydederken, diğeri artık geçersiz olan
 * AYNI eski refresh token'ı kullanmaya çalışıp reddediliyor ve
 * `clearAuthStorage()` çağırıp BİRAZ ÖNCE başarıyla yenilenmiş GEÇERLİ
 * oturumu siliyordu. Bu dosya yalnızca o regresyonun deterministik testini
 * içerir (iOS'un `AuthEnvironment.inFlightRefresh` testiyle AYNI amaç).
 */
describe("api.ts — concurrent refresh de-duplication", () => {
  beforeEach(() => {
    localStorage.setItem("token", "old-token");
    localStorage.setItem("refresh_token", "old-refresh-token");
    localStorage.setItem("user_id", "1");
    localStorage.setItem("email", "u@test.com");
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("two concurrent 401s share a single /auth/refresh request, both succeed with the refreshed token", async () => {
    let refreshCallCount = 0;

    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      const headers = (init?.headers ?? {}) as Record<string, string>;

      if (url.includes("/auth/refresh")) {
        refreshCallCount += 1;
        return new Response(
          JSON.stringify({
            access_token: "new-token",
            refresh_token: "new-refresh-token",
            user_id: 1,
            email: "u@test.com",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      if (url.includes("/trips")) {
        if (headers.Authorization === "Bearer old-token") {
          return new Response(
            JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Oturum süresi doldu." } }),
            { status: 401, headers: { "Content-Type": "application/json" } }
          );
        }
        if (headers.Authorization === "Bearer new-token") {
          return new Response(JSON.stringify({ trips: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
      }

      throw new Error(`Beklenmeyen fetch çağrısı: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    // `optimize/page.tsx`'in `Promise.all([...])`'ı ile AYNI şekil: iki
    // bağımsız authenticated istek eşzamanlı ateşlenir, ikisi de aynı anda
    // 401 alır.
    const [first, second] = await Promise.all([getTrips(), getTrips()]);

    expect(first).toEqual({ trips: [] });
    expect(second).toEqual({ trips: [] });
    expect(refreshCallCount).toBe(1);
    expect(localStorage.getItem("token")).toBe("new-token");
  });
});
