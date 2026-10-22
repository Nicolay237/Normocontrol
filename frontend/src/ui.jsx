import {
  ArrowLeft, ArrowRight, BookOpen, Check, ChevronDown, CircleAlert, CircleCheck, CircleCheckBig, Download,
  AlignJustify, FileText, FileUp, GraduationCap, IndentIncrease, Info, Lightbulb, ListChecks, OctagonAlert, Scan, Type,
  WandSparkles, LogIn, LogOut, CircleUserRound, Shield, KeyRound, Users, UserPlus, Lock, Copy, Trash2, RotateCcw,
  Ban, Eye, EyeOff, Search, Gift,
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
  gift: Gift,
};

/** Логотип: страница с полями (пунктир — левое поле) и отметкой «проверено». Цвета — из темы. */
export const Logo = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo">
    <rect width="32" height="32" rx="8" fill="var(--md-sys-color-primary)" /><rect x="8" y="5" width="16" height="22" rx="2" fill="var(--md-sys-color-on-primary)" /><path d="M12 7.5v17" stroke="var(--md-sys-color-primary)" strokeWidth="1.2" strokeDasharray="1.6 1.2" opacity="0.75" /><path d="M14 10.5h7M14 14h7M14 17.5h4.5" stroke="var(--md-sys-color-primary)" strokeWidth="1.6" strokeLinecap="round" opacity="0.55" /><circle cx="23" cy="23" r="6.2" fill="var(--md-sys-color-tertiary)" stroke="var(--md-sys-color-primary)" strokeWidth="1.6" /><path d="M20.3 23.1l1.8 1.8 3.5-3.7" stroke="var(--md-sys-color-on-tertiary)" strokeWidth="1.7" fill="none" strokeLinecap="round" strokeLinejoin="round" />
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
