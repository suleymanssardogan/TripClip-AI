import { describe, it, expect, vi, afterEach } from "vitest";
import { getSession, getTrips, login } from "./api";

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
      if (url.endsWith("/trips")) {
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
