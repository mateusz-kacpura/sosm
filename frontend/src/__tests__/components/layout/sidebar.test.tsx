import { render, screen } from "@testing-library/react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";

describe("Sidebar", () => {
  it("renders the logo", () => {
    render(<Sidebar />);
    expect(screen.getByText("SOSM Panel")).toBeInTheDocument();
  });

  it("renders all 4 navigation links", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Konta FB")).toBeInTheDocument();
    expect(screen.getByText("Kampanie")).toBeInTheDocument();
    expect(screen.getByText("Historia Logów")).toBeInTheDocument();
  });

  it("renders logout button", () => {
    render(<Sidebar />);
    expect(screen.getByText("Wyloguj")).toBeInTheDocument();
  });

  it("highlights active link based on pathname", () => {
    vi.mocked(usePathname).mockReturnValue("/accounts");
    render(<Sidebar />);
    const accountsLink = screen.getByText("Konta FB").closest("a");
    expect(accountsLink?.className).toContain("bg-primary");
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink?.className).not.toContain("bg-primary");
  });
});
