import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "@/app/page";

const mockStats = {
  active_campaigns: 3,
  total_accounts: 4,
  posts_today: 24,
  success_rate: "95%",
};

const mockLogs = [
  { id: 1, campaign_name: "Kampania A", status: "SUCCESS", executed_at: "2024-03-11T10:15:00Z" },
  { id: 2, campaign_name: "Kampania B", status: "FAILED", error_message: "Timeout", executed_at: "2024-03-11T09:00:00Z" },
];

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/stats/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockStats),
            statusText: "OK",
          });
        }
        if (url.includes("/logs/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockLogs),
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

  it("renders page heading", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
  });

  it("renders stats cards with API values", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
    });
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("renders stat card titles", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Aktywne Kampanie")).toBeInTheDocument();
    });
    expect(screen.getByText("Konta Facebook")).toBeInTheDocument();
    expect(screen.getByText("Posty (Dzisiaj)")).toBeInTheDocument();
    expect(screen.getByText("Skuteczność")).toBeInTheDocument();
  });

  it("renders recent activity table with API data", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Ostatnie Aktywności")).toBeInTheDocument();
    });
    expect(screen.getByText("Kampania A")).toBeInTheDocument();
    expect(screen.getByText("Kampania B")).toBeInTheDocument();
  });

  it("shows success and failed badges", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Sukces")).toBeInTheDocument();
    });
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, statusText: "Server Error" }))
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/Błąd/)).toBeInTheDocument();
    });
  });

  it("shows loading state initially", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Ładowanie statystyk...")).toBeInTheDocument();
  });

  it("shows empty logs message when no logs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/stats/")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockStats),
            statusText: "OK",
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
          statusText: "OK",
        });
      })
    );
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Brak logów")).toBeInTheDocument();
    });
  });
});
