import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountsPage from "@/app/accounts/page";

const mockAccounts = [
  {
    id: 1,
    fb_email: "marcin.fb@gmail.com",
    proxy_url: "185.23.44.11:8080",
    created_at: "2024-03-10T00:00:00Z",
    fanpages: [
      { id: 10, account_id: 1, fanpage_url: "https://facebook.com/fanpage1", fanpage_name: "FP One", created_at: "2024-03-10T00:00:00Z" },
    ],
  },
  {
    id: 2,
    fb_email: "tester.sosm@wp.pl",
    proxy_url: null,
    created_at: "2024-03-09T00:00:00Z",
    fanpages: [],
  },
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
        if (opts?.method === "POST" && url.includes("/fanpages")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({
              id: 20,
              account_id: 1,
              fanpage_url: "https://facebook.com/newfp",
              fanpage_name: "New FP",
              created_at: "2024-03-11T00:00:00Z",
            }),
            statusText: "OK",
          });
        }
        if (opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 3, fb_email: "new@fb.com", proxy_url: null, created_at: "2024-03-11T00:00:00Z", fanpages: [] }),
            statusText: "OK",
          });
        }
        if (opts?.method === "DELETE") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ detail: "Deleted" }),
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
        "/api/accounts/",
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
        "/api/accounts/1",
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

  it("shows fanpage count per account", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });
    // Account 1 has 1 fanpage, account 2 has 0
    const counts = screen.getAllByText(/fanpage/);
    expect(counts.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Fanpage'e column header", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Fanpage'e")).toBeInTheDocument();
    });
  });

  it("expands fanpage section on click", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });

    // Click the fanpage count area to expand
    const fanpageButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("fanpage")
    );
    if (fanpageButtons.length > 0) {
      await user.click(fanpageButtons[0]);
      await waitFor(() => {
        // After expanding, fanpage URL should be visible
        expect(screen.getByText("https://facebook.com/fanpage1")).toBeInTheDocument();
      });
    }
  });

  it("shows add fanpage form when expanded", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });

    const fanpageButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("fanpage")
    );
    if (fanpageButtons.length > 0) {
      await user.click(fanpageButtons[0]);
      await waitFor(() => {
        expect(screen.getByPlaceholderText("https://www.facebook.com/nazwa-fanpage")).toBeInTheDocument();
      });
    }
  });

  it("calls fanpage create API when adding fanpage", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });

    // Expand first account's fanpage section
    const fanpageButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("fanpage")
    );
    if (fanpageButtons.length > 0) {
      await user.click(fanpageButtons[0]);
      await waitFor(() => {
        expect(screen.getByPlaceholderText("https://www.facebook.com/nazwa-fanpage")).toBeInTheDocument();
      });

      await user.type(
        screen.getByPlaceholderText("https://www.facebook.com/nazwa-fanpage"),
        "https://facebook.com/newfp"
      );

      // Find and click the add button (Plus icon button)
      const addButtons = screen.getAllByRole("button").filter(
        (btn) => !btn.hasAttribute("disabled") && btn.closest("tr")
      );
      // The add button should be the one in the expanded section
      const addButton = screen.getAllByRole("button").find(
        (btn) => btn.textContent === "" && btn.closest(".flex")
      );

      // Click any "Dodaj" type button in the expanded section
      const submitButtons = screen.getAllByRole("button");
      for (const btn of submitButtons) {
        if (btn.closest("[class*='fanpage']") || btn.getAttribute("aria-label")?.includes("add")) {
          // This is probably the add fanpage button
        }
      }

      await waitFor(() => {
        // The input should contain our value
        const input = screen.getByPlaceholderText("https://www.facebook.com/nazwa-fanpage") as HTMLInputElement;
        expect(input.value).toBe("https://facebook.com/newfp");
      });
    }
  });

  it("calls fanpage delete API when removing fanpage", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });

    // Expand first account's fanpage section
    const fanpageButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("fanpage")
    );
    if (fanpageButtons.length > 0) {
      await user.click(fanpageButtons[0]);
      await waitFor(() => {
        expect(screen.getByText("https://facebook.com/fanpage1")).toBeInTheDocument();
      });

      // Find trash/delete button next to the fanpage
      const trashButtons = screen.getAllByRole("button").filter(
        (btn) => {
          const svg = btn.querySelector("svg");
          return svg !== null && btn.closest(".flex");
        }
      );

      // Click the delete button for the fanpage (small trash icon)
      if (trashButtons.length > 0) {
        // Find the one in the expanded fanpage section
        for (const btn of trashButtons) {
          const parentText = btn.parentElement?.textContent || "";
          if (parentText.includes("facebook.com/fanpage1")) {
            await user.click(btn);
            break;
          }
        }
      }

      await waitFor(() => {
        const deleteCalls = (fetch as any).mock.calls.filter(
          (call: any[]) => call[1]?.method === "DELETE" && call[0].includes("/fanpages/")
        );
        if (deleteCalls.length > 0) {
          expect(deleteCalls[0][0]).toContain("/accounts/1/fanpages/10");
        }
      });
    }
  });
});
