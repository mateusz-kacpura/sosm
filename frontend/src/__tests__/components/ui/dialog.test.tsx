import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

describe("Dialog", () => {
  it("does not show content when closed", () => {
    render(
      <Dialog open={false}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hidden Title</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
    expect(screen.queryByText("Hidden Title")).not.toBeInTheDocument();
  });

  it("shows content when open", async () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Visible Title</DialogTitle>
            <DialogDescription>Some description</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
    await waitFor(() => {
      expect(screen.getByText("Visible Title")).toBeInTheDocument();
    });
    expect(screen.getByText("Some description")).toBeInTheDocument();
  });

  it("renders close button with sr-only text", async () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogTitle>T</DialogTitle>
        </DialogContent>
      </Dialog>
    );
    await waitFor(() => {
      expect(screen.getByText("Close")).toBeInTheDocument();
    });
  });
});
