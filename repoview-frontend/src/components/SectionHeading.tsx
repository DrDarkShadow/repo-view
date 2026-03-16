interface SectionHeadingProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  centered?: boolean;
}

export function SectionHeading({ eyebrow, title, subtitle, centered = true }: SectionHeadingProps) {
  return (
    <div className={centered ? 'text-center' : ''}>
      {eyebrow && (
        <p className="text-brand-accent text-sm font-semibold uppercase tracking-wider mb-2">
          {eyebrow}
        </p>
      )}
      <h2 className="section-heading mb-4 text-white">{title}</h2>
      {subtitle && (
        <p className="text-gray-400 text-lg leading-relaxed max-w-2xl mx-auto">
          {subtitle}
        </p>
      )}
    </div>
  );
}
