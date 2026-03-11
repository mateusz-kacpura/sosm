import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CampaignsPage from "@/app/campaigns/page";

const mockCampaigns = [
  { id: 1, name: "Promocja Kursu AI", account_id: 1, groups: [{}, {}, {}], status: "AKTYWNA", start_at: null },
  { id: 2, name: "Wyprzedaż Garażowa", account_id: 2, groups: [{}, {}], status: "WSTRZYMANA", start_at: "2024-06-01T12:00:00Z" },
];

const mockAccounts = [
  { id: 1, fb_email: "marcin@fb.com" },
  { id: 2, fb_email: "tester@fb.com" },
];

describe("CampaignsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, opts?: any) => {
        if (url.includes("/campaigns/") && (!opts || !opts.method)) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockCampaigns),
            statusText: "OK",
          });
        }
        if (url.includes("/accounts/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockAccounts),
            statusText: "OK",
          });
        }
        if (opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 3, name: "Test", status: "SZKIC", groups: [] }),
            statusText: "OK",
          });
        }
        if (opts?.method === "PATCH") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 1, status: "WSTRZYMANA" }),
            statusText: "OK",
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page title", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampanie Automatyzacji")).toBeInTheDocument();
    });
  });

  it("renders campaign table with API data", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Promocja Kursu AI")).toBeInTheDocument();
    });
    expect(screen.getByText("Wyprzedaż Garażowa")).toBeInTheDocument();
  });

  it("shows groups count badges", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText(/3 grup/)).toBeInTheDocument();
    });
    expect(screen.getByText(/2 grup/)).toBeInTheDocument();
  });

  it("shows campaign status badges", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Aktywna")).toBeInTheDocument();
    });
    expect(screen.getByText("Wstrzymana")).toBeInTheDocument();
  });

  it("opens new campaign dialog", async () => {
    const user = userEvent.setup();
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nowa Kampania")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Nowa Kampania"));
    await waitFor(() => {
      expect(screen.getByText("Kreator Nowej Kampanii")).toBeInTheDocument();
    });
  });

  it("shows start_at or 'Od razu' for campaigns", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Od razu")).toBeInTheDocument();
    });
  });

  it("shows action buttons based on status", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Wstrzymaj")).toBeInTheDocument();
    });
    expect(screen.getByText("Wznów")).toBeInTheDocument();
  });

  it("shows empty state when no campaigns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/accounts/")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Brak kampanii")).toBeInTheDocument();
    });
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, statusText: "Server Error" }))
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Błąd/)).toBeInTheDocument();
    });
  });

  it("calls PATCH API when clicking Wstrzymaj", async () => {
    const user = userEvent.setup();
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Wstrzymaj")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Wstrzymaj"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8010/api/campaigns/1",
        expect.objectContaining({ method: "PATCH" })
      );
    });
  });

  it("submits new campaign form with groups", async () => {
    const user = userEvent.setup();
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nowa Kampania")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Nowa Kampania"));
    await waitFor(() => {
      expect(screen.getByText("Kreator Nowej Kampanii")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("np. Letnia Promocja"), "Test Kampania");
    await user.type(screen.getByPlaceholderText("URL grupy"), "https://facebook.com/groups/test");
    await user.type(screen.getByPlaceholderText("Treść posta dla tej grupy"), "Treść testowa");

    // Select account
    await user.selectOptions(screen.getByRole("combobox"), "1");

    await user.click(screen.getByText("Utwórz Kampanię"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8010/api/campaigns/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("shows Szkic status badge for draft campaigns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/campaigns/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([{ id: 10, name: "Draft", account_id: 1, groups: [], status: "SZKIC", start_at: null }]),
            statusText: "OK",
          });
        }
        if (url.includes("/accounts/")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(mockAccounts), statusText: "OK" });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Szkic")).toBeInTheDocument();
    });
    // "Start" appears both as table header and button - use getAllByText
    const startElements = screen.getAllByText("Start");
    expect(startElements.length).toBeGreaterThanOrEqual(2);
  });

  it("shows Zakończona status badge", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/campaigns/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([{ id: 10, name: "Done", account_id: 1, groups: [], status: "ZAKOŃCZONA", start_at: null }]),
            statusText: "OK",
          });
        }
        if (url.includes("/accounts/")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(mockAccounts), statusText: "OK" });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Zakończona")).toBeInTheDocument();
    });
  });
});
