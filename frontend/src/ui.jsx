import {
  ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, CircleAlert, CircleCheck, CircleCheckBig, Download,
  AlignJustify, FileText, FileUp, GraduationCap, IndentIncrease, Info, Lightbulb, ListChecks, OctagonAlert, Scan, Type,
  WandSparkles,
} from "lucide-react";

// Custom elements в React 18 получают атрибуты как строки: disabled={false} стал бы "false" (= включено),
// поэтому булевы атрибуты передаём через эту функцию.
export const attr = (cond) => (cond ? "" : undefined);

const ICONS = {
  brand: CircleCheckBig,
  error: CircleAlert,
  info: Info,
  chevron: ChevronDown,
  ok: CircleCheck,
  report: OctagonAlert,
  file: FileText,
  upload: FileUp,
  hint: Lightbulb,
  vkr: GraduationCap,
  coursework: BookOpen,
  forward: ArrowRight,
  back: ArrowLeft,
  download: Download,
  fix: WandSparkles,
  check: ListChecks,
  tick: Check,
  font: Type,
  spacing: AlignJustify,
  indent: IndentIncrease,
  margins: Scan,
};

/** Иконка Lucide по короткому имени. Лишние props (например slot="icon" для кнопок M3) уходят на <svg>. */
export const Icon = ({ name, size = 24, ...props }) => {
  const Cmp = ICONS[name];
  return Cmp ? <Cmp size={size} strokeWidth={1.75} aria-hidden="true" {...props} /> : null;
};
