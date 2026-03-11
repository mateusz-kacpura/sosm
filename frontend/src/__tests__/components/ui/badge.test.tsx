import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders with text content", () => {
    render(<Badge>Status</Badge>);
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders default variant", () => {
    const { container } = render(<Badge>Default</Badge>);
    const badge = container.querySelector("[data-slot='badge']");
    expect(badge?.className).toContain("bg-primary");
  });

  it("renders destructive variant", () => {
    const { container } = render(<Badge variant="destructive">Error</Badge>);
    const badge = container.querySelector("[data-slot='badge']");
    expect(badge?.className).toContain("bg-destructive");
  });
});
