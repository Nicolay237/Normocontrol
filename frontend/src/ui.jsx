import {
  ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, CircleAlert, CircleCheck, CircleCheckBig, Download,
  AlignJustify, FileText, FileUp, GraduationCap, IndentIncrease, Info, Lightbulb, ListChecks, OctagonAlert, Scan, Type,
  WandSparkles, LogIn, LogOut, CircleUserRound, Shield, KeyRound, Users, UserPlus, Lock, Copy, Trash2, RotateCcw,
  Ban, Eye, EyeOff, Search,
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
  login: LogIn,
  logout: LogOut,
  user: CircleUserRound,
  admin: Shield,
  key: KeyRound,
  users: Users,
  userAdd: UserPlus,
  lock: Lock,
  copy: Copy,
  trash: Trash2,
  reset: RotateCcw,
  block: Ban,
  eye: Eye,
  eyeOff: EyeOff,
  search: Search,
};

/** Логотип: штамп нормоконтроля «НК». Цвета берутся из темы. */
export const Logo = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo">
    <g transform="rotate(-12 16 16)">
      <circle cx="16" cy="16" r="14.5" fill="var(--md-sys-color-primary)" />
      <circle cx="16" cy="16" r="11.6" fill="none" stroke="var(--md-sys-color-on-primary)"
              strokeWidth="1.2" strokeDasharray="2.2 1.4" />
      <text x="16" y="20.2" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif"
            fontWeight="700" fontSize="12" fill="var(--md-sys-color-on-primary)">НК</text>
    </g>
  </svg>
);

/** Иконка Lucide по короткому имени. Лишние props (например slot="icon" для кнопок M3) уходят на <svg>. */
export const Icon = ({ name, size = 24, ...props }) => {
  const Cmp = ICONS[name];
  return Cmp ? <Cmp size={size} strokeWidth={1.75} aria-hidden="true" {...props} /> : null;
};

/**
 * Enter в текстовом поле отправляет форму. Браузер делает это сам только при наличии
 * нативной кнопки отправки, а md-filled-button ею не считается.
 */
export function submitOnEnter(e) {
  if (e.key !== "Enter" || e.target.tagName !== "INPUT" || e.nativeEvent.isComposing) return;
  e.preventDefault();
  e.currentTarget.requestSubmit();
}

/** Текстовое поле в стиле M3 (outlined) на нативном <input>: работают автозаполнение и менеджеры паролей. */
export function Field({ label, hint, error, className = "", ...props }) {
  return (
    <label className={`field ${error ? "field-error" : ""} ${className}`}>
      <span className="field-label label-large">{label}</span>
      <input className="field-input body-large" {...props} />
      {(error || hint) && <span className="field-hint body-medium">{error || hint}</span>}
    </label>
  );
}
