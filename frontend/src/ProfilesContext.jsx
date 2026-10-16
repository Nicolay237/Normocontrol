import { createContext, useContext, useEffect, useState } from "react";
import { fetchProfiles, fetchConfig } from "./api.js";

const Ctx = createContext({ profiles: null, error: null, config: { autofix_enabled: false } });

export function ProfilesProvider({ children }) {
  const [state, setState] = useState({ profiles: null, error: null, config: { autofix_enabled: false } });
  useEffect(() => {
    fetchProfiles()
      .then((list) => setState((s) => ({ ...s, profiles: Object.fromEntries(list.map((p) => [p.key, p])), error: null })))
      .catch((e) => setState((s) => ({ ...s, profiles: null, error: e.message })));
    fetchConfig()
      .then((config) => setState((s) => ({ ...s, config })))
      .catch(() => {}); // без конфига просто не показываем автоисправление
  }, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useProfiles = () => useContext(Ctx);
