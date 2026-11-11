import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, hasToken, login as doLogin, setToken } from "./api";
import type { Role, User } from "./types";

interface Ctx { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; logout: () => void; can: (...roles: Role[]) => boolean }
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(hasToken());
  useEffect(() => {
    if (!hasToken()) return;
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);
  const value: Ctx = {
    user, loading,
    login: async (e, p) => setUser(await doLogin(e, p)),
    logout: () => { setToken(null); setUser(null); },
    can: (...roles) => !!user && roles.includes(user.role),
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
