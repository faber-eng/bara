type SectionHeadProps = { id: string; eyebrow: string; title: string };

export function SectionHead({ id, eyebrow, title }: SectionHeadProps) {
  return (
    <header className="landing-head">
      <p className="eyebrow landing-eyebrow">{eyebrow}</p>
      <h2 id={id} className="landing-h2">
        {title}
      </h2>
    </header>
  );
}
