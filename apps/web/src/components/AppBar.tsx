import { Link } from "@tanstack/react-router";
import { EmberMark } from "./EmberMark";

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
        <Link to="/join">Join</Link>
      </nav>
    </header>
  );
}
