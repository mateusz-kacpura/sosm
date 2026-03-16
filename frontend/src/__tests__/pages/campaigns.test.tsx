import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CampaignsPage from "@/app/campaigns/page";

const mockCampaigns = [
  { id: 1, name: "Promocja Kursu AI", account_id: 1, groups_count: 3, status: "AKTYWNA", created_at: "2024-03-10T00:00:00Z" },
  { id: 2, name: "Wyprzedaż Garażowa", account_id: 2, groups_count: 2, status: "WSTRZYMANA", created_at: "2024-06-01T12:00:00Z" },
];

describe("CampaignsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, opts?: any) => {
        if (url.includes("/campaigns/") && (!opts || !opts.method || opts.method === "GET")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockCampaigns),
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

  it("shows new campaign button linking to /campaigns/new", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nowa Kampania")).toBeInTheDocument();
    });
    const link = screen.getByText("Nowa Kampania").closest("a");
    expect(link).toHaveAttribute("href", "/campaigns/new");
  });

  it("shows action buttons based on status", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Wstrzymaj")).toBeInTheDocument();
    });
    expect(screen.getByText("Wznow")).toBeInTheDocument();
  });

  it("shows empty state when no campaigns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" })
      )
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
      expect(screen.getByText(/Blad/)).toBeInTheDocument();
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
        "/api/campaigns/1",
        expect.objectContaining({ method: "PATCH" })
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
            json: () => Promise.resolve([{ id: 10, name: "Draft", account_id: 1, groups_count: 0, status: "SZKIC", created_at: null }]),
            statusText: "OK",
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Szkic")).toBeInTheDocument();
    });
    const startElements = screen.getAllByText("Start");
    expect(startElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Zakonczona status badge", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/campaigns/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([{ id: 10, name: "Done", account_id: 1, groups_count: 0, status: "ZAKOŃCZONA", created_at: null }]),
            statusText: "OK",
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
      })
    );
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Zakonczona")).toBeInTheDocument();
    });
  });
});
