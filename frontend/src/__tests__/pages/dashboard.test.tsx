import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "@/app/page";

describe("DashboardPage", () => {
  it("renders page heading", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
  });

  it("renders stats cards with values", async () => {
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

  it("renders recent activity table", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Ostatnie Aktywności")).toBeInTheDocument();
    });
    expect(screen.getByText("Giełda Warszawa")).toBeInTheDocument();
    expect(screen.getByText("Programiści PL")).toBeInTheDocument();
  });

  it("shows success and failed badges", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Sukces")).toHaveLength(3);
    });
    expect(screen.getByText("Błąd")).toBeInTheDocument();
  });
});
