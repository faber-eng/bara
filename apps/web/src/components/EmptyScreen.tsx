export function EmptyScreen({ title, path }: { title: string; path: string }) {
  return (
    <section className="screen-center">
      <p className="eyebrow">App shell</p>
      <h1 className="screen-title">{title}</h1>
      <p className="lede">This route is empty on purpose. Its screen is built behind this URL.</p>
      <p>
        <span className="spec-code">{path}</span>
      </p>
    </section>
  );
}
