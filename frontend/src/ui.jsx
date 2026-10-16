// Custom elements в React 18 получают атрибуты как строки: disabled={false} стал бы "false" (= включено),
// поэтому булевы атрибуты передаём через эту функцию.
export const attr = (cond) => (cond ? "" : undefined);

export const Icon = ({ name }) => (
  <span className="material-symbols-outlined" aria-hidden="true">{name}</span>
);
