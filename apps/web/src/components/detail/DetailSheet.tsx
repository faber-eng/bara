import {
  createContext,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
  type SyntheticEvent,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
} from "react";
import type { FactGroup, FactRow } from "./facts";

type SheetContext = { titleId: string; closeLabel: string; onClose: () => void };

const DetailSheetContext = createContext<SheetContext | null>(null);

function useSheet(): SheetContext {
  const context = useContext(DetailSheetContext);
  if (context === null) throw new Error("DetailLayout must render inside a DetailSheet");
  return context;
}

function focusedElement(): HTMLElement | null {
  const active = document.activeElement;
  return active instanceof HTMLElement ? active : null;
}

type DetailSheetProps = { closeLabel: string; onClose: () => void; children: ReactNode };

export function DetailSheet({ closeLabel, onClose, children }: DetailSheetProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return;
    const opener = focusedElement();
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onClose();
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>) {
    event.preventDefault();
    onClose();
  }

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === event.currentTarget) onClose();
  }

  return (
    <DetailSheetContext.Provider value={{ titleId, closeLabel, onClose }}>
      <dialog
        ref={dialogRef}
        className="mv-sheet"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
        onCancel={handleCancel}
        onClick={handleBackdropClick}
      >
        <div className="mv-sheet-body">{children}</div>
      </dialog>
    </DetailSheetContext.Provider>
  );
}

type DetailLayoutProps = { title: string; chips?: ReactNode; children: ReactNode };

export function DetailLayout({ title, chips, children }: DetailLayoutProps) {
  const { titleId, closeLabel, onClose } = useSheet();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  return (
    <>
      <header className="mv-sheet-head">
        <div className="mv-sheet-heading">
          <h2 id={titleId} className="mv-sheet-title">
            {title}
          </h2>
          {chips !== undefined && <div className="mv-sheet-chips">{chips}</div>}
        </div>
        <button
          ref={closeRef}
          type="button"
          className="btn-icon mv-close"
          aria-label={closeLabel}
          onClick={onClose}
        >
          <span aria-hidden="true">×</span>
        </button>
      </header>
      {children}
    </>
  );
}

type SectionProps = { label: string; children: ReactNode };

export function DetailSection({ label, children }: SectionProps) {
  return (
    <section className="mv-section" aria-label={label}>
      <h3 className="mv-heading">{label}</h3>
      {children}
    </section>
  );
}

export function DetailText({ label, children }: SectionProps) {
  return (
    <DetailSection label={label}>
      <p className="mv-text">{children}</p>
    </DetailSection>
  );
}

export function DetailAbout({ label, children }: SectionProps) {
  return (
    <details className="mv-about">
      <summary>{label}</summary>
      <p className="mv-text">{children}</p>
    </details>
  );
}

type KeyFactProps = {
  label?: string;
  value: ReactNode;
  caption?: ReactNode;
  aside?: ReactNode;
};

export function DetailKeyFact({ label, value, caption, aside }: KeyFactProps) {
  return (
    <div className="mv-keyfact">
      <div className="mv-keyfact-main">
        {label !== undefined && <p className="mv-keyfact-label">{label}</p>}
        <p className="mv-keyfact-value num">{value}</p>
        {caption !== undefined && <p className="mv-keyfact-caption">{caption}</p>}
      </div>
      {aside !== undefined && <div className="mv-keyfact-aside">{aside}</div>}
    </div>
  );
}

function FactItem({ row }: { row: FactRow }) {
  return (
    <div className="mv-fact">
      <dt>{row.label}</dt>
      <dd>
        <span className="mv-fact-value num">{row.value}</span>
        {row.meaning !== null && <span className="mv-fact-meaning">{row.meaning}</span>}
      </dd>
    </div>
  );
}

type FactListProps = { rows: readonly FactRow[]; heading?: string };

export function FactList({ rows, heading }: FactListProps) {
  if (rows.length === 0) return null;
  return (
    <div className="mv-fact-group">
      {heading !== undefined && <h4 className="mv-subheading">{heading}</h4>}
      <dl className="mv-facts">
        {rows.map((row) => (
          <FactItem key={row.label} row={row} />
        ))}
      </dl>
    </div>
  );
}

export function FactSection({ label, rows }: { label: string; rows: readonly FactRow[] }) {
  if (rows.length === 0) return null;
  return (
    <DetailSection label={label}>
      <FactList rows={rows} />
    </DetailSection>
  );
}

type FactGroupsProps = { label: string; groups: readonly FactGroup[] };

export function FactGroupsSection({ label, groups }: FactGroupsProps) {
  return (
    <DetailSection label={label}>
      {groups.map((group) => (
        <FactList key={group.heading} heading={group.heading} rows={group.rows} />
      ))}
    </DetailSection>
  );
}

export function DetailActions({ children }: { children: ReactNode }) {
  return <div className="mv-actions">{children}</div>;
}
