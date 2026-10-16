import { createContext, useContext, useEffect, useState } from "react";
import { fetchProfiles } from "./api.js";

const Ctx = createContext({ profiles: null, error: null });

export function ProfilesProvider({ children }) {
  const [state, setState] = useState({ profiles: null, error: null });
  useEffect(() => {
    fetchProfiles()
      .then((list) => setState({ profiles: Object.fromEntries(list.map((p) => [p.key, p])), error: null }))
      .catch((e) => setState({ profiles: null, error: e.message }));
  }, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useProfiles = () => useContext(Ctx);
