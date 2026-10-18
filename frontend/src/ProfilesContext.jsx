import { createContext, useContext, useEffect, useState } from "react";
import { fetchProfiles, fetchConfig } from "./api.js";

const DEFAULT_CONFIG = { autofix_enabled: false };
const toMap = (list) => Object.fromEntries(list.map((p) => [p.key, p]));

// Сервер вставляет профили и конфиг прямо в index.html (window.__BOOT__) —
// страница рисуется сразу, без двух дополнительных запросов (важно на мобильном интернете).
const boot = typeof window !== "undefined" ? window.__BOOT__ : null;

const Ctx = createContext({ profiles: null, error: null, config: DEFAULT_CONFIG });

export function ProfilesProvider({ children }) {
  const [state, setState] = useState(() => ({
    profiles: boot?.profiles ? toMap(boot.profiles) : null,
    config: boot?.config ?? DEFAULT_CONFIG,
    error: null,
  }));

  useEffect(() => {
    if (boot?.profiles) return; // всё уже есть (режим разработки через Vite идёт без __BOOT__)
    fetchProfiles()
      .then((list) => setState((s) => ({ ...s, profiles: toMap(list), error: null })))
      .catch((e) => setState((s) => ({ ...s, profiles: null, error: e.message })));
    fetchConfig()
      .then((config) => setState((s) => ({ ...s, config })))
      .catch(() => {}); // без конфига просто не показываем автоисправление
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useProfiles = () => useContext(Ctx);
