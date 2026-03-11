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
      "http://localhost:8010/api/accounts/",
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
      "http://localhost:8010/api/test",
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
      "http://localhost:8010/api/accounts/",
      expect.anything()
    );
  });

  it("accounts.create sends POST", async () => {
    await api.accounts.create({ email: "a@b.com" });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/accounts/",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("campaigns.update sends PATCH with id", async () => {
    await api.campaigns.update(5, { status: "active" });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/campaigns/5",
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("logs.list calls correct endpoint", async () => {
    await api.logs.list();
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/logs/",
      expect.anything()
    );
  });
});
