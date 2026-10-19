import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

const KEY = "theme";
const MODES = [
  { id: "system", label: "Тема: как в системе", Icon: Monitor },
  { id: "light", label: "Тема: светлая", Icon: Sun },
  { id: "dark", label: "Тема: тёмная", Icon: Moon },
];
const BAR_COLOR = { light: "#fceae9", dark: "#271d1d" }; // цвет строки браузера на телефоне

function readMode() {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

/** Применяет тему: data-theme на <html> (стили в theme.css) и цвет строки браузера. */
export function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "system") delete root.dataset.theme;
  else root.dataset.theme = mode;
  const dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
    if (mode === "system") m.setAttribute("content", m.media.includes("dark") ? BAR_COLOR.dark : BAR_COLOR.light);
    else m.setAttribute("content", dark ? BAR_COLOR.dark : BAR_COLOR.light);
  });
}

/** Кнопка в шапке: по нажатию «как в системе» → «светлая» → «тёмная». Выбор запоминается. */
export default function ThemeToggle() {
  const [mode, setMode] = useState(readMode);

  useEffect(() => {
    applyTheme(mode);
    try {
      if (mode === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, mode);
    } catch { /* приватный режим — просто не запоминаем */ }
  }, [mode]);

  const i = MODES.findIndex((m) => m.id === mode);
  const next = MODES[(i + 1) % MODES.length];
  const { Icon, label } = MODES[i];

  return (
    <button
      type="button"
      className="icon-btn theme-btn"
      onClick={() => setMode(next.id)}
      aria-label={`${label}. Нажмите, чтобы переключить`}
      title={`${label} (нажмите — ${next.label.replace("Тема: ", "")})`}
    >
      <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
    </button>
  );
}
