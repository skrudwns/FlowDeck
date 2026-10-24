export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function Loading({ label = "불러오는 중" }: { label?: string }) {
  return <p className="text-sm text-zinc-500">{label}…</p>;
}
