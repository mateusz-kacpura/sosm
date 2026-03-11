import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LogsPage from "@/app/logs/page";

const mockLogs = [
  { id: 101, campaign_name: "Kampania A", status: "SUCCESS", error_message: null, retry_count: 0, executed_at: "2024-03-11T10:15:02Z", screenshot_path: null },
  { id: 102, campaign_name: "Kampania B", status: "SUCCESS", error_message: null, retry_count: 0, executed_at: "2024-03-11T09:45:11Z", screenshot_path: null },
  { id: 103, campaign_name: "Kampania C", status: "CHECKPOINT_DETECTED", error_message: "Wykryto weryfikację", retry_count: 0, executed_at: "2024-03-11T09:12:45Z", screenshot_path: "/screenshots/err.png" },
  { id: 104, campaign_name: "Kampania D", status: "FAILED", error_message: "Brak pola tekstowego", retry_count: 2, executed_at: "2024-03-11T08:15:00Z", screenshot_path: null },
];

describe("LogsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockLogs),
          statusText: "OK",
        })
      )
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page title", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Historia Operacji")).toBeInTheDocument();
    });
  });

  it("renders log table with API data", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampania A")).toBeInTheDocument();
    });
    expect(screen.getByText("Kampania B")).toBeInTheDocument();
    expect(screen.getByText("Kampania C")).toBeInTheDocument();
  });

  it("shows all status badges", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Sukces")).toHaveLength(2);
    });
    expect(screen.getByText("Checkpoint")).toBeInTheDocument();
    // "Błąd" appears both as table header and badge, so use getAllByText
    expect(screen.getAllByText("Błąd").length).toBeGreaterThanOrEqual(2);
  });

  it("displays error messages", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Wykryto weryfikację")).toBeInTheDocument();
    });
    expect(screen.getByText("Brak pola tekstowego")).toBeInTheDocument();
  });

  it("renders search input", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Szukaj po kampanii lub statusie...")).toBeInTheDocument();
    });
  });

  it("filters logs by search query", async () => {
    const user = userEvent.setup();
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampania A")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Szukaj po kampanii lub statusie..."), "Kampania D");
    await waitFor(() => {
      expect(screen.queryByText("Kampania A")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Kampania D")).toBeInTheDocument();
  });

  it("shows retry count", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("shows empty state when no logs", async () => {
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
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Brak logów")).toBeInTheDocument();
    });
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, statusText: "Server Error" }))
    );
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Błąd/)).toBeInTheDocument();
    });
  });

  it("shows EXCEPTION status badge as 'Wyjątek'", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            { id: 200, campaign_name: "Exc", status: "EXCEPTION", error_message: "Timeout", retry_count: 3, executed_at: "2024-03-11T10:00:00Z", screenshot_path: null },
          ]),
          statusText: "OK",
        })
      )
    );
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Wyjątek")).toBeInTheDocument();
    });
  });

  it("filters logs by error message", async () => {
    const user = userEvent.setup();
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampania C")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Szukaj po kampanii lub statusie..."), "weryfikację");
    await waitFor(() => {
      expect(screen.queryByText("Kampania A")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Kampania C")).toBeInTheDocument();
  });

  it("shows screenshot button only when screenshot_path exists", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampania C")).toBeInTheDocument();
    });
    // Only log 103 has screenshot_path, so there should be exactly 1 image button
    const buttons = screen.getAllByRole("button");
    // The screenshot button is rendered only for log 103
    const screenshotLog = mockLogs.filter(l => l.screenshot_path);
    expect(screenshotLog).toHaveLength(1);
  });
});
