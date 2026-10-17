import { Link } from "@tanstack/react-router";

function EmberMark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M16 3c1.8 4.6 7.5 8.2 7.5 15.1A7.5 7.5 0 0 1 8.5 18c0-3.4 1.6-5.6 3.4-7.4.2 2.4 1.2 4 2.8 4.8C14.2 11 14.6 6.8 16 3z"
        fill="var(--vivid-lime)"
      />
      <path
        d="M16 17.5c1 1.8 3 3 3 5.4a3 3 0 0 1-6 0c0-1.7 1-2.8 3-5.4z"
        fill="var(--forest-ink)"
      />
    </svg>
  );
}

export function AppBar() {
  return (
    <header className="appbar on-dark">
      <Link to="/" className="logo">
        <EmberMark />
        <span>bara</span>
      </Link>
      <nav className="appbar-nav" aria-label="Screens">
        <Link to="/public">Public</Link>
        <Link to="/ops">Ops</Link>
        <Link to="/brigade">Brigade</Link>
        <Link to="/area/new">Draw an area</Link>
      </nav>
    </header>
  );
}
