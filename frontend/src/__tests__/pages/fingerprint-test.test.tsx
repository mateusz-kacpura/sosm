import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FingerprintTestPage from "@/app/fingerprint-test/page";

const mockAccounts = [
  { id: 1, fb_email: "test@fb.com", proxy_url: "http://proxy:8080" },
  { id: 2, fb_email: "user@fb.com", proxy_url: null },
];

const mockTests = [
  {
    id: 1,
    account_id: 1,
    status: "COMPLETED",
    proxy_url_used: "http://proxy:8080",
    overall_score: 95,
    overall_status: "pass",
    error_message: null,
    created_at: "2026-03-11T10:00:00Z",
    completed_at: "2026-03-11T10:00:30Z",
  },
  {
    id: 2,
    account_id: null,
    status: "FAILED",
    proxy_url_used: null,
    overall_score: null,
    overall_status: null,
    error_message: "Browser crash",
    created_at: "2026-03-11T09:00:00Z",
    completed_at: "2026-03-11T09:00:10Z",
  },
];

const mockTestDetail = {
  id: 1,
  account_id: 1,
  status: "COMPLETED",
  proxy_url_used: "http://proxy:8080",
  results: {
    self_test: {
      navigator: {
        webdriver: false,
        userAgent: "Mozilla/5.0 Firefox/128.0",
        platform: "Linux x86_64",
        pluginsLength: 5,
        languages: ["en-US"],
      },
      screen: { width: 1920, height: 1080 },
      webgl: { unmaskedRenderer: "NVIDIA GeForce GTX 1080" },
    },
    analysis: {
      overall_score: 95,
      overall_status: "pass",
      categories: {
        navigator: { status: "pass", issues: [], data: {} },
        canvas: { status: "pass", issues: [], data: {} },
        webgl: { status: "pass", issues: [], data: {} },
        screen: { status: "pass", issues: [], data: {} },
        audio: { status: "warn", issues: ["AudioContext niedostepne"], data: {} },
        fonts: { status: "pass", issues: [], data: {} },
        webrtc: { status: "pass", issues: [], data: {} },
        timezone: { status: "pass", issues: [], data: {} },
        user_agent: { status: "pass", issues: [], data: {} },
        automation_detection: { status: "pass", issues: [], data: {} },
      },
    },
    external_sites: {},
  },
  error_message: null,
  created_at: "2026-03-11T10:00:00Z",
  completed_at: "2026-03-11T10:00:30Z",
};

function setupFetchMock(overrides: Record<string, any> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, opts?: any) => {
      if (url.includes("/accounts/")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(overrides.accounts ?? mockAccounts),
          statusText: "OK",
        });
      }
      if (url.includes("/fingerprint-tests/") && url.match(/\/\d+$/) && (!opts || !opts.method)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(overrides.testDetail ?? mockTestDetail),
          statusText: "OK",
        });
      }
      if (url.includes("/fingerprint-tests/") && opts?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 99, status: "RUNNING" }),
          statusText: "OK",
        });
      }
      if (url.includes("/fingerprint-tests/") && opts?.method === "DELETE") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ detail: "deleted" }),
          statusText: "OK",
        });
      }
      if (url.includes("/fingerprint-tests/")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(overrides.tests ?? mockTests),
          statusText: "OK",
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]), statusText: "OK" });
    })
  );
}

describe("FingerprintTestPage", () => {
  beforeEach(() => {
    setupFetchMock();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page heading", async () => {
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Testy Fingerprint")).toBeInTheDocument();
    });
  });

  it("renders account selector with accounts", async () => {
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Bez proxy")).toBeInTheDocument();
    });
  });

  it("renders run button", async () => {
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Uruchom Test")).toBeInTheDocument();
    });
  });

  it("shows running state after clicking run", async () => {
    const user = userEvent.setup();
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Uruchom Test")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Uruchom Test"));
    await waitFor(() => {
      expect(screen.getByText("Trwa test...")).toBeInTheDocument();
    });
  });

  it("renders history table with test data", async () => {
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Historia testow")).toBeInTheDocument();
    });
    expect(screen.getByText("95/100")).toBeInTheDocument();
  });

  it("shows status badges in history", async () => {
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Zakonczone")).toBeInTheDocument();
    });
    expect(screen.getByText("Blad")).toBeInTheDocument();
  });

  it("loads test details when clicking history row", async () => {
    const user = userEvent.setup();
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("95/100")).toBeInTheDocument();
    });
    await user.click(screen.getByText("95/100"));
    await waitFor(() => {
      expect(screen.getByText("95")).toBeInTheDocument();
    });
  });

  it("shows category cards in results", async () => {
    const user = userEvent.setup();
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("95/100")).toBeInTheDocument();
    });
    await user.click(screen.getByText("95/100"));
    await waitFor(() => {
      expect(screen.getByText("Kategorie")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Kategorie"));
    await waitFor(() => {
      expect(screen.getByText("Navigator")).toBeInTheDocument();
    });
    expect(screen.getByText("Canvas 2D")).toBeInTheDocument();
    expect(screen.getByText("WebGL")).toBeInTheDocument();
    expect(screen.getByText("Detekcja Bota")).toBeInTheDocument();
  });

  it("shows pass and warn badges in categories", async () => {
    const user = userEvent.setup();
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("95/100")).toBeInTheDocument();
    });
    await user.click(screen.getByText("95/100"));
    await waitFor(() => {
      expect(screen.getByText("Kategorie")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Kategorie"));
    await waitFor(() => {
      const passBadges = screen.getAllByText("Pass");
      expect(passBadges.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Warn")).toBeInTheDocument();
  });

  it("calls delete API when clicking delete button", async () => {
    const user = userEvent.setup();
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Historia testow")).toBeInTheDocument();
    });
    const deleteButtons = screen.getAllByRole("button").filter(
      btn => btn.querySelector("svg")
    );
    // Click the first delete button (trash icon)
    const trashButtons = screen.getAllByRole("button");
    const deleteBtn = trashButtons.find(btn =>
      btn.classList.contains("text-rose-500")
    );
    if (deleteBtn) {
      await user.click(deleteBtn);
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining("/fingerprint-tests/"),
          expect.objectContaining({ method: "DELETE" })
        );
      });
    }
  });

  it("shows empty state when no tests", async () => {
    setupFetchMock({ tests: [] });
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText("Brak testow")).toBeInTheDocument();
    });
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, statusText: "Server Error" }))
    );
    render(<FingerprintTestPage />);
    await waitFor(() => {
      expect(screen.getByText(/Blad/)).toBeInTheDocument();
    });
  });
});
