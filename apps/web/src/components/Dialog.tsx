import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  "button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex='-1'])";

type DialogProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
};

function focusablesIn(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
}

function wrapTab(event: KeyboardEvent<HTMLElement>, root: HTMLElement) {
  const items = focusablesIn(root);
  const first = items[0];
  const last = items[items.length - 1];
  if (!first || !last) return;
  const active = document.activeElement;
  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

export function Dialog({ title, onClose, children }: DialogProps) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement;
    const root = panel.current;
    if (root) focusablesIn(root)[0]?.focus();
    return () => {
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key === "Tab" && panel.current) wrapTab(event, panel.current);
  }

  return createPortal(
    // biome-ignore lint/a11y/noStaticElementInteractions: the backdrop only dismisses; Esc and Cancel are the keyboard paths
    <div className="dialog-backdrop" onMouseDown={onClose} onKeyDown={handleKeyDown}>
      <div
        ref={panel}
        className="dialog-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id={titleId} className="dialog-title">
          {title}
        </h2>
        {children}
      </div>
    </div>,
    document.body,
  );
}
