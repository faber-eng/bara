import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { DetailAbout, DetailKeyFact, DetailLayout, DetailSheet, FactSection } from "./DetailSheet";

function Harness({ onClose = () => {} }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);

  function close() {
    onClose();
    setOpen(false);
  }

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        riau-0102
      </button>
      {open && (
        <DetailSheet closeLabel="Close" onClose={close}>
          <DetailLayout title="Area riau-0102">
            <DetailKeyFact value="96.8 / 100" caption="Very fast drying · Rank 1 of 3,769" />
            <FactSection
              label="Numbers"
              rows={[{ label: "Rain, 30 days", value: "182.6 mm", meaning: null }]}
            />
            <DetailAbout label="What it is">This square is a 1 km peat area.</DetailAbout>
          </DetailLayout>
        </DetailSheet>
      )}
    </>
  );
}

function openFromRow() {
  const row = screen.getByRole("button", { name: "riau-0102" });
  row.focus();
  fireEvent.click(row);
  return row;
}

describe("DetailSheet", () => {
  it("opens as a modal dialog named by its title, with the close button focused", () => {
    render(<Harness />);
    openFromRow();

    const dialog = screen.getByRole("dialog", { name: "Area riau-0102" });
    expect(dialog).toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    expect(dialog).toHaveTextContent("96.8 / 100");
    expect(dialog).toHaveTextContent("Very fast drying · Rank 1 of 3,769");
    expect(within(dialog).getByRole("heading", { level: 3, name: "Numbers" })).toBeInTheDocument();
  });

  it("keeps the generic explainer collapsed until asked", () => {
    render(<Harness />);
    openFromRow();

    const summary = screen.getByText("What it is");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(summary);
    expect(summary.closest("details")).toHaveAttribute("open");
  });

  it("closes on Escape and returns focus to the row that opened it", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const row = openFromRow();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(row).toHaveFocus();
  });

  it("closes from the close button and from a click on the backdrop", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    openFromRow();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    openFromRow();
    fireEvent.click(screen.getByRole("dialog"));

    expect(onClose).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays open on a click inside the sheet", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    openFromRow();

    fireEvent.click(screen.getByText("96.8 / 100"));

    expect(onClose).not.toHaveBeenCalled();
  });
});
