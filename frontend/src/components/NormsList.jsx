export default function NormsList({ norms }) {
  return (
    <section className="norms">
      <h2>Что проверяется</h2>
      <dl className="norms-grid">
        {norms.map((n) => (
          <div key={n.name} className="norm-card">
            <dt>{n.name}</dt>
            <dd>{n.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
