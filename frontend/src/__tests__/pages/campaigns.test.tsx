import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CampaignsPage from "@/app/campaigns/page";

describe("CampaignsPage", () => {
  it("renders page title", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Kampanie Automatyzacji")).toBeInTheDocument();
    });
  });

  it("renders campaign table with mock data", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Promocja Kursu AI")).toBeInTheDocument();
    });
    expect(screen.getByText("Wyprzedaż Garażowa")).toBeInTheDocument();
  });

  it("shows groups count badges", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText(/12 grup/)).toBeInTheDocument();
    });
    expect(screen.getByText(/5 grup/)).toBeInTheDocument();
  });

  it("shows campaign status badges", async () => {
    render(<CampaignsPage />);
    await waitFor(() => {
      expect(screen.getByText("Aktywna")).toBeInTheDocument();
    });
    expect(screen.getByText("Wstrzymana")).toBeInTheDocument();
  });

  it("opens new campaign dialog", async () => {
    const user = userEvent.setup();
    render(<CampaignsPage />);
    await user.click(screen.getByText("Nowa Kampania"));
    await waitFor(() => {
      expect(screen.getByText("Kreator Nowej Kampanii")).toBeInTheDocument();
    });
  });

  it("creates new campaign via form", async () => {
    const user = userEvent.setup();
    render(<CampaignsPage />);
    await user.click(screen.getByText("Nowa Kampania"));
    await waitFor(() => {
      expect(screen.getByText("Kreator Nowej Kampanii")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("np. Letnia Promocja"), "Test Campaign");
    await user.type(
      screen.getByPlaceholderText("https://facebook.com/groups/..."),
      "https://facebook.com/groups/1\nhttps://facebook.com/groups/2"
    );
    await user.type(
      screen.getByPlaceholderText("Cześć wszystkim! Chciałbym zaprosić..."),
      "Hello world"
    );
    await user.click(screen.getByText("Uruchom Kampanię"));

    await waitFor(() => {
      expect(screen.getByText("Test Campaign")).toBeInTheDocument();
    });
  });
});
