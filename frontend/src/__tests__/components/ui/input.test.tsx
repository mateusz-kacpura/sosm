import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "@/components/ui/input";

describe("Input", () => {
  it("renders with placeholder", () => {
    render(<Input placeholder="Enter text..." />);
    expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
  });

  it("accepts typed input", async () => {
    const user = userEvent.setup();
    render(<Input placeholder="type here" />);
    const input = screen.getByPlaceholderText("type here");
    await user.type(input, "hello");
    expect(input).toHaveValue("hello");
  });

  it("supports password type", () => {
    render(<Input type="password" placeholder="pass" />);
    expect(screen.getByPlaceholderText("pass")).toHaveAttribute("type", "password");
  });
});
