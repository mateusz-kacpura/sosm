import { render, screen } from "@testing-library/react";
import { NodePalette } from "@/components/workflow/node-palette";

describe("NodePalette", () => {
  it("renders category headers", () => {
    render(<NodePalette />);
    expect(screen.getByText("Trigger")).toBeInTheDocument();
    expect(screen.getByText("Facebook")).toBeInTheDocument();
    expect(screen.getByText("Flow")).toBeInTheDocument();
    expect(screen.getByText("Utility")).toBeInTheDocument();
  });

  it("renders Węzły header", () => {
    render(<NodePalette />);
    expect(screen.getByText("Węzły")).toBeInTheDocument();
  });

  it("renders trigger nodes", () => {
    render(<NodePalette />);
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("Koniec")).toBeInTheDocument();
  });

  it("renders facebook nodes", () => {
    render(<NodePalette />);
    expect(screen.getByText("Logowanie FB")).toBeInTheDocument();
    expect(screen.getByText("Post na grupie")).toBeInTheDocument();
    expect(screen.getByText("Post na fanpage")).toBeInTheDocument();
    expect(screen.getByText("Polub stronę")).toBeInTheDocument();
    expect(screen.getByText("Komentarz")).toBeInTheDocument();
    expect(screen.getByText("Wyślij wiadomość")).toBeInTheDocument();
  });

  it("renders flow nodes", () => {
    render(<NodePalette />);
    expect(screen.getByText("Czekaj")).toBeInTheDocument();
    expect(screen.getByText("Warunek")).toBeInTheDocument();
    expect(screen.getByText("Pętla")).toBeInTheDocument();
    expect(screen.getByText("Losowy wybór")).toBeInTheDocument();
    expect(screen.getByText("Złącz")).toBeInTheDocument();
  });

  it("renders utility nodes", () => {
    render(<NodePalette />);
    expect(screen.getByText("Zmienna")).toBeInTheDocument();
    expect(screen.getByText("Webhook")).toBeInTheDocument();
  });

  it("all items are draggable", () => {
    const { container } = render(<NodePalette />);
    const draggables = container.querySelectorAll("[draggable=true]");
    // 2 trigger + 6 facebook + 5 flow + 2 utility = 15 items
    expect(draggables.length).toBe(15);
  });
});
