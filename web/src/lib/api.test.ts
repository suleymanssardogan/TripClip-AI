import { describe, it, expect, vi, afterEach } from "vitest";
import { getSession, getTrips, login, getPlans, getUserPlans } from "./api";

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("cookie-backed web session", () => {
  it("shares one refresh request across concurrent 401 responses", async () => {
    let refreshed = false;
    let refreshCalls = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      expect(init?.credentials).toBe("include");
      expect((init?.headers as Record<string, string>)?.Authorization).toBeUndefined();
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        refreshed = true;
        return new Response(JSON.stringify({ user_id: 1, email: "u@test.com" }), { status: 200 });
      }
      if (new URL(url, "http://localhost").pathname.endsWith("/trips")) {
        return new Response(JSON.stringify(refreshed ? { trips: [] } : { detail: "expired" }), {
          status: refreshed ? 200 : 401,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([getTrips(), getTrips()]);
    expect(first).toEqual({ trips: [] });
    expect(second).toEqual({ trips: [] });
    expect(refreshCalls).toBe(1);
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("gets session metadata after refreshing an expired access cookie", async () => {
    let refreshed = false;
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/auth/refresh")) {
        refreshed = true;
        return new Response(JSON.stringify({ user_id: 2, email: "user@test.com" }));
      }
      if (url.endsWith("/auth/session")) {
        return new Response(JSON.stringify(refreshed ? { user_id: 2, email: "user@test.com" } : { code: "SESSION_EXPIRED" }), {
          status: refreshed ? 200 : 401,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    expect(await getSession()).toEqual({ user_id: 2, email: "user@test.com" });
  });

  it("does not call refresh for an anonymous visitor", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ code: "NO_SESSION" }), { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await getSession()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not persist login credentials in localStorage", async () => {
    localStorage.setItem("token", "legacy-token");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ user_id: 1, email: "u@test.com" }))));
    expect(await login("u@test.com", "password")).toEqual({ user_id: 1, email: "u@test.com" });
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});


describe("plan card response normalization", () => {
  it("shows the BFF location count in both public and account lists", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      plans: [{ id: 48, filename: "antalya.mp4", status: "completed", locationsCount: 17,
        topLocation: "Antalya", ocrPreview: ["Hidayet Koyu"], processingTime: 25.85 }],
      total: 1, has_more: false,
    }))));
    for (const page of [await getPlans(), await getUserPlans(17)]) {
      expect(page.plans[0].locations_count).toBe(17);
      expect(page.plans[0].top_location).toBe("Antalya");
      expect(page.plans[0].ocr_preview).toEqual(["Hidayet Koyu"]);
      expect(page.plans[0].processing_time).toBe(25.85);
      expect(page.total).toBe(1);
    }
  });

  it("preserves summaries supplied in the original snake_case format", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ plans: [{
      id: 1, locations_count: 4, top_location: "Kaş", processing_time: 0, ocr_preview: [],
    }], total: 1, has_more: true }))));
    const page = await getUserPlans(17);
    expect(page.plans[0].locations_count).toBe(4);
    expect(page.plans[0].processing_time).toBe(0);
    expect(page.has_more).toBe(true);
  });
});
