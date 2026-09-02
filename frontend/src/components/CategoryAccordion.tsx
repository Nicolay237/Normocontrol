import type { ReportCategory } from '../api/types.ts'

interface CategoryAccordionProps {
  readonly category: ReportCategory
}

export function CategoryAccordion({ category }: CategoryAccordionProps) {
  return (
    <details className="nc-category" open>
      <summary>
        <span className="nc-category__name">{category.name}</span>
        <span className="nc-category__count">{category.issues.length}</span>
      </summary>
      <table className="nc-category__table">
        <tbody>
          {category.issues.map((issue, index) => (
            // Locations are not guaranteed unique across issues in the same category
            // (e.g. repeated table cells), so pair them with the index for a stable key.
            <tr key={`${issue.location}-${index}`}>
              <td className="nc-category__loc">{issue.location}</td>
              <td>{issue.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}
