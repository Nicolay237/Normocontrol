import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { fetchProfiles, fetchConfig } from "./api.js";

const DEFAULT_CONFIG = { autofix_enabled: false, user: null };
const toMap = (list) => Object.fromEntries(list.map((p) => [p.key, p]));

// Сервер вставляет профили, конфиг и текущего пользователя прямо в index.html (window.__BOOT__) —
// страница рисуется сразу, без дополнительных запросов (важно на мобильном интернете).
const boot = typeof window !== "undefined" ? window.__BOOT__ : null;

const Ctx = createContext({ profiles: null, error: null, config: DEFAULT_CONFIG, setSession: () => {} });

export function ProfilesProvider({ children }) {
  const [state, setState] = useState(() => ({
    profiles: boot?.profiles ? toMap(boot.profiles) : null,
    config: { ...DEFAULT_CONFIG, ...(boot?.config || {}) },
    error: null,
  }));

  useEffect(() => {
    if (boot?.profiles) return; // всё уже есть (режим разработки через Vite идёт без __BOOT__)
    fetchProfiles()
      .then((list) => setState((s) => ({ ...s, profiles: toMap(list), error: null })))
      .catch((e) => setState((s) => ({ ...s, profiles: null, error: e.message })));
    fetchConfig()
      .then((config) => setState((s) => ({ ...s, config: { ...DEFAULT_CONFIG, ...config } })))
      .catch(() => {});
  }, []);

  /** После входа/выхода/смены пароля: ответ API {user, autofix_enabled}. */
  const setSession = useCallback(({ user, autofix_enabled }) => {
    setState((s) => ({ ...s, config: { ...s.config, user: user ?? null, autofix_enabled: !!autofix_enabled } }));
  }, []);

  return <Ctx.Provider value={{ ...state, setSession }}>{children}</Ctx.Provider>;
}

export const useProfiles = () => useContext(Ctx);
export const useSession = () => {
  const { config, setSession } = useContext(Ctx);
  return { user: config.user, autofixEnabled: config.autofix_enabled, setSession };
};
