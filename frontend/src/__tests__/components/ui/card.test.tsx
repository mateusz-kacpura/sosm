import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

describe("Card", () => {
  it("renders card with all sub-components", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Content body</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Content body")).toBeInTheDocument();
    expect(screen.getByText("Footer")).toBeInTheDocument();
  });

  it("applies data-slot attributes", () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>T</CardTitle>
        </CardHeader>
      </Card>
    );
    expect(container.querySelector("[data-slot='card']")).toBeInTheDocument();
    expect(container.querySelector("[data-slot='card-header']")).toBeInTheDocument();
    expect(container.querySelector("[data-slot='card-title']")).toBeInTheDocument();
  });

  it("accepts custom className", () => {
    const { container } = render(<Card className="custom-class">C</Card>);
    expect(container.querySelector("[data-slot='card']")?.className).toContain("custom-class");
  });
});
