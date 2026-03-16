import { render, screen } from "@testing-library/react";
import RootLayout, { metadata } from "@/app/layout";

// Mock next/font/google
vi.mock("next/font/google", () => ({
  Inter: () => ({ className: "inter-mock" }),
}));

// Mock AuthProvider to pass-through children
vi.mock("@/components/auth/auth-provider", () => ({
  AuthProvider: ({ children }: any) => children,
  useAuth: () => ({ logout: vi.fn(), authenticated: true, loading: false }),
}));

describe("RootLayout", () => {
  it("renders children content", () => {
    render(
      <RootLayout>
        <div data-testid="child">Test Content</div>
      </RootLayout>
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });

  it("renders sidebar", () => {
    render(
      <RootLayout>
        <div>Content</div>
      </RootLayout>
    );
    // Sidebar contains "SOSM Panel" logo text
    expect(screen.getByText("SOSM Panel")).toBeInTheDocument();
  });

  it("has correct html lang attribute", () => {
    const { container } = render(
      <RootLayout>
        <div>Content</div>
      </RootLayout>
    );
    const html = container.closest("html");
    expect(html).toHaveAttribute("lang", "pl");
  });

  it("wraps content in main element", () => {
    render(
      <RootLayout>
        <div data-testid="child">Content</div>
      </RootLayout>
    );
    const main = screen.getByRole("main");
    expect(main).toBeInTheDocument();
    expect(main).toContainElement(screen.getByTestId("child"));
  });
});

describe("metadata", () => {
  it("has correct title", () => {
    expect(metadata.title).toBe("SOSM Panel - Obsidian & Gold");
  });

  it("has correct description", () => {
    expect(metadata.description).toBe("System Obsługi Social Media Automation");
  });
});
