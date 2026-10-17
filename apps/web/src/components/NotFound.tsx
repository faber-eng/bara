import { Link } from "@tanstack/react-router";

export function NotFound() {
  return (
    <section className="screen-center">
      <p className="eyebrow">Not found</p>
      <h1 className="screen-title">This page does not exist.</h1>
      <p>
        <Link to="/" className="btn btn-primary">
          Go to the start
        </Link>
      </p>
    </section>
  );
}
