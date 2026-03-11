import { render, screen, waitFor } from "@testing-library/react";
import LogsPage from "@/app/logs/page";

describe("LogsPage", () => {
  it("renders page title", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Historia Operacji")).toBeInTheDocument();
    });
  });

  it("renders log table with mock data", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("user1@fb.com")).toHaveLength(2);
    });
    expect(screen.getByText("Giełda Warszawa")).toBeInTheDocument();
    expect(screen.getByText("Programiści PL")).toBeInTheDocument();
  });

  it("shows all three status badges", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Sukces")).toHaveLength(3);
    });
    expect(screen.getByText("Checkpoint")).toBeInTheDocument();
    expect(screen.getByText("Błąd")).toBeInTheDocument();
  });

  it("displays log details", async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Opublikowano pomyślnie")).toHaveLength(3);
    });
    expect(screen.getByText("Wykryto weryfikację tożsamości")).toBeInTheDocument();
  });

  it("renders search input", () => {
    render(<LogsPage />);
    expect(screen.getByPlaceholderText("Szukaj po koncie lub grupie...")).toBeInTheDocument();
  });
});
