export default function NormsList({ norms }) {
  return (
    <section className="norms">
      <h2 className="headline-small">Что проверяется</h2>
      <dl className="card-grid card-grid-sm">
        {norms.map((n) => (
          <div key={n.name} className="card card-outlined">
            <dt className="title-medium">{n.name}</dt>
            <dd className="body-medium">{n.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
