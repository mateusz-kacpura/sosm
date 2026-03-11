import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountsPage from "@/app/accounts/page";

const mockAccounts = [
  { id: 1, fb_email: "marcin.fb@gmail.com", proxy_url: "185.23.44.11:8080", created_at: "2024-03-10T00:00:00Z" },
  { id: 2, fb_email: "tester.sosm@wp.pl", proxy_url: null, created_at: "2024-03-09T00:00:00Z" },
];

describe("AccountsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, opts?: any) => {
        if (url.includes("/accounts/") && (!opts || !opts.method || opts.method === "GET")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockAccounts),
            statusText: "OK",
          });
        }
        if (opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 3, fb_email: "new@fb.com", proxy_url: null, created_at: "2024-03-11T00:00:00Z" }),
            statusText: "OK",
          });
        }
        if (opts?.method === "DELETE") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ detail: "Account deleted" }),
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
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Konta Facebook")).toBeInTheDocument();
    });
  });

  it("renders account table with API data", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });
    expect(screen.getByText("tester.sosm@wp.pl")).toBeInTheDocument();
    expect(screen.getByText("185.23.44.11:8080")).toBeInTheDocument();
  });

  it("shows add account button", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Dodaj Konto")).toBeInTheDocument();
    });
  });

  it("opens dialog when clicking add button", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Dodaj Konto")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Dodaj Konto"));
    await waitFor(() => {
      expect(screen.getByText("Nowe Konto Facebook")).toBeInTheDocument();
    });
  });

  it("submits new account form", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Dodaj Konto")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Dodaj Konto"));
    await waitFor(() => {
      expect(screen.getByText("Nowe Konto Facebook")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("example@email.com"), "new@fb.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "secret123");
    await user.click(screen.getByText("Zapisz Konto"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8010/api/accounts/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("shows delete buttons for each account", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      const deleteButtons = screen.getAllByText("Usuń");
      expect(deleteButtons.length).toBe(2);
    });
  });

  it("calls delete API when clicking delete", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Usuń").length).toBe(2);
    });

    await user.click(screen.getAllByText("Usuń")[0]);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8010/api/accounts/1",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("shows empty state when no accounts", async () => {
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
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Brak kont")).toBeInTheDocument();
    });
  });

  it("shows 'Brak' for null fields", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      const brakCells = screen.getAllByText("Brak");
      expect(brakCells.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, statusText: "Server Error" }))
    );
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Błąd/)).toBeInTheDocument();
    });
  });
});
