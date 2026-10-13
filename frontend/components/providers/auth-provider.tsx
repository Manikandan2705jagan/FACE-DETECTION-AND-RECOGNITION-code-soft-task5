"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api, getToken, setToken } from "@/lib/api";
import type { Role, User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
}

const RANK: Record<Role, number> = { viewer: 0, auditor: 1, operator: 2, admin: 3 };

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      const token = await api.login(email, password);
      setToken(token.access_token);
      const me = await api.me();
      setUser(me);
      router.push("/dashboard");
    },
    [router],
  );

  const logout = React.useCallback(() => {
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  const hasRole = React.useCallback(
    (...roles: Role[]) => {
      if (!user) return false;
      return roles.some((r) => RANK[user.role] >= RANK[r]);
    },
    [user],
  );

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}
