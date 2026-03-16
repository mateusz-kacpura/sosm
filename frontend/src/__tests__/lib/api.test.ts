import { fetchApi, api } from "@/lib/api";

describe("fetchApi", () => {
  const mockResponse = { data: "test" };

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockResponse),
          statusText: "OK",
        })
      )
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls fetch with correct URL", async () => {
    await fetchApi("/accounts/");
    expect(fetch).toHaveBeenCalledWith(
      "/api/accounts/",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      })
    );
  });

  it("returns parsed JSON on success", async () => {
    const result = await fetchApi("/test");
    expect(result).toEqual(mockResponse);
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          statusText: "Not Found",
        })
      )
    );
    await expect(fetchApi("/missing")).rejects.toThrow("API Error: Not Found");
  });

  it("passes custom options", async () => {
    await fetchApi("/test", { method: "POST", body: '{"a":1}' });
    expect(fetch).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        method: "POST",
        body: '{"a":1}',
      })
    );
  });
});

describe("api object", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
          statusText: "OK",
        })
      )
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("accounts.list calls correct endpoint", async () => {
    await api.accounts.list();
    expect(fetch).toHaveBeenCalledWith(
      "/api/accounts/",
      expect.anything()
    );
  });

  it("accounts.create sends POST", async () => {
    await api.accounts.create({ fb_email: "a@b.com", fb_password: "pass" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/accounts/",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("accounts.delete sends DELETE with id", async () => {
    await api.accounts.delete(3);
    expect(fetch).toHaveBeenCalledWith(
      "/api/accounts/3",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("campaigns.update sends PATCH with id", async () => {
    await api.campaigns.update(5, { status: "AKTYWNA" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/campaigns/5",
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("campaigns.groups calls correct endpoint", async () => {
    await api.campaigns.groups(7);
    expect(fetch).toHaveBeenCalledWith(
      "/api/campaigns/7/groups",
      expect.anything()
    );
  });

  it("logs.list calls correct endpoint", async () => {
    await api.logs.list();
    expect(fetch).toHaveBeenCalledWith(
      "/api/logs/",
      expect.anything()
    );
  });

  it("stats calls correct endpoint", async () => {
    await api.stats();
    expect(fetch).toHaveBeenCalledWith(
      "/api/stats/",
      expect.anything()
    );
  });
});
