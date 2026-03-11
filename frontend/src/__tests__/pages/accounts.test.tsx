import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountsPage from "@/app/accounts/page";

describe("AccountsPage", () => {
  it("renders page title", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("Konta Facebook")).toBeInTheDocument();
    });
  });

  it("renders account table with mock data", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText("marcin.fb@gmail.com")).toBeInTheDocument();
    });
    expect(screen.getByText("tester.sosm@wp.pl")).toBeInTheDocument();
    expect(screen.getByText("185.23.44.11:8080")).toBeInTheDocument();
  });

  it("shows add account button", () => {
    render(<AccountsPage />);
    expect(screen.getByText("Dodaj Konto")).toBeInTheDocument();
  });

  it("opens dialog when clicking add button", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);
    await user.click(screen.getByText("Dodaj Konto"));
    await waitFor(() => {
      expect(screen.getByText("Nowe Konto Facebook")).toBeInTheDocument();
    });
  });

  it("adds new account via form submission", async () => {
    const user = userEvent.setup();
    render(<AccountsPage />);

    await user.click(screen.getByText("Dodaj Konto"));
    await waitFor(() => {
      expect(screen.getByText("Nowe Konto Facebook")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("example@email.com"), "new@fb.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "secret123");
    await user.click(screen.getByText("Zapisz Konto"));

    await waitFor(() => {
      expect(screen.getByText("new@fb.com")).toBeInTheDocument();
    });
  });

  it("displays account statuses", async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      const statuses = screen.getAllByText("Aktywne");
      expect(statuses.length).toBeGreaterThanOrEqual(2);
    });
  });
});
