export default function NormsList({ norms }) {
  return (
    <section className="norms">
      <h2 className="title-large section-title">Что проверяется</h2>
      <dl className="norms-card">
        {norms.map((n) => (
          <div key={n.name} className="norm-row">
            <dt className="title-medium">{n.name}</dt>
            <dd className="body-medium">{n.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
