import './FeatureGrid.css'

interface Feature {
  readonly title: string
  readonly description: string
}

const FEATURES: readonly Feature[] = [
  {
    title: 'Поля страницы',
    description: 'Левое, правое, верхнее и нижнее поля сверяются с допустимыми отклонениями.',
  },
  {
    title: 'Шрифт и кегль',
    description: 'Times New Roman 14 пт для основного текста — с исключением для формул.',
  },
  {
    title: 'Межстрочный интервал',
    description: 'Полуторный интервал абзацев, включая PDF без явных метаданных форматирования.',
  },
  {
    title: 'Красная строка',
    description: 'Отступ первой строки 1,25 см — без ложных срабатываний на списках.',
  },
  {
    title: 'Заголовки',
    description: 'Полужирное начертание и отсутствие точки в конце — оглавление не считается.',
  },
  {
    title: 'Расположение нарушения',
    description: 'Каждое замечание указывает страницу и абзац, а не сквозной номер по документу.',
  },
]

export function FeatureGrid() {
  return (
    <section className="nc-features" aria-labelledby="nc-features-heading">
      <h2 id="nc-features-heading">Что проверяется</h2>
      <div className="nc-features__grid">
        {FEATURES.map((feature) => (
          <div className="nc-feature-card" key={feature.title}>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
