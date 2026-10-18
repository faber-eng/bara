import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { DetailLayout, DetailSheet, DetailText, FactList } from "./DetailSheet";

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
          <DetailLayout title="Area riau-0102" chips={<span className="chip">Rank 1</span>}>
            <DetailText label="What it is">This square is a 1 km peat area.</DetailText>
            <FactList
              label="Numbers"
              rows={[{ label: "Drying score", value: "96.8 / 100", meaning: "Very fast drying" }]}
            />
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
    expect(dialog).toHaveTextContent("This square is a 1 km peat area.");
    expect(dialog).toHaveTextContent("96.8 / 100");
    expect(dialog).toHaveTextContent("Very fast drying");
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

    fireEvent.click(screen.getByText("This square is a 1 km peat area."));

    expect(onClose).not.toHaveBeenCalled();
  });
});
