import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WorkflowsPage from "@/app/workflows/page";

const mockWorkflows = [
  {
    id: 1,
    name: "Auto Post Workflow",
    description: "Posts to groups automatically",
    account_id: 1,
    status: "AKTYWNY",
    node_count: 5,
    last_run_status: "COMPLETED",
    created_at: "2026-03-01T12:00:00Z",
  },
  {
    id: 2,
    name: "Like & Comment",
    description: null,
    account_id: null,
    status: "SZKIC",
    node_count: 3,
    last_run_status: null,
    created_at: "2026-03-10T08:00:00Z",
  },
];

describe("WorkflowsPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, opts?: any) => {
        if (url.includes("/workflows/") && opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ id: 3, name: "Nowy workflow" }),
            statusText: "OK",
          });
        }
        if (url.includes("/workflows/") && opts?.method === "DELETE") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ status: "deleted" }),
            statusText: "OK",
          });
        }
        if (url.includes("/workflows")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockWorkflows),
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
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Workflows")).toBeInTheDocument();
    });
  });

  it("renders subtitle", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Buduj przepływy automatyzacji/)).toBeInTheDocument();
    });
  });

  it("renders workflow table with API data", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Auto Post Workflow")).toBeInTheDocument();
    });
    expect(screen.getByText("Like & Comment")).toBeInTheDocument();
  });

  it("shows workflow descriptions", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Posts to groups automatically")).toBeInTheDocument();
    });
  });

  it("shows status badges", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Aktywny")).toBeInTheDocument();
    });
    expect(screen.getByText("Szkic")).toBeInTheDocument();
  });

  it("shows node counts", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
    });
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows last run status", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    });
  });

  it("shows dash for no last run", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });

  it("shows Nowy Workflow button", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nowy Workflow")).toBeInTheDocument();
    });
  });

  it("shows empty state when no workflows", async () => {
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
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Brak workflows/)).toBeInTheDocument();
    });
  });

  it("shows table headers", async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nazwa")).toBeInTheDocument();
    });
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Węzły")).toBeInTheDocument();
    expect(screen.getByText("Ostatni run")).toBeInTheDocument();
    expect(screen.getByText("Utworzono")).toBeInTheDocument();
    expect(screen.getByText("Akcje")).toBeInTheDocument();
  });

  it("calls create API on Nowy Workflow click", async () => {
    const user = userEvent.setup();
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText("Nowy Workflow")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Nowy Workflow"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/workflows/"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});
