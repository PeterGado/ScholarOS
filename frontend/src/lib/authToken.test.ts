import { describe, expect, it, beforeEach, vi } from "vitest";
import { getToken, setToken, subscribeToToken } from "./authToken";

describe("authToken", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setToken(null);
  });

  it("returns null when no token has ever been set", () => {
    expect(getToken()).toBeNull();
  });

  it("persists a set token to localStorage and returns it", () => {
    setToken("abc123");
    expect(getToken()).toBe("abc123");
    expect(window.localStorage.getItem("scholaros.token")).toBe("abc123");
  });

  it("clears localStorage when set to null", () => {
    setToken("abc123");
    setToken(null);
    expect(getToken()).toBeNull();
    expect(window.localStorage.getItem("scholaros.token")).toBeNull();
  });

  it("notifies subscribers on every change", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToToken(listener);

    setToken("xyz");
    expect(listener).toHaveBeenCalledWith("xyz");

    unsubscribe();
    setToken(null);
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
