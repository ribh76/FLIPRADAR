import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  apiClient,
  clearAuthSession,
  getStoredAccessToken,
  storeAuthSession,
} from "../services/apiClient";
import type { AuthSession, CurrentUser } from "../types";

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoadingUser: boolean;
  isSessionExpired: boolean;
  user: CurrentUser | null;
  login: (session: AuthSession) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<CurrentUser | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [hasToken, setHasToken] = useState(() =>
    Boolean(getStoredAccessToken()),
  );
  const [isLoadingUser, setIsLoadingUser] = useState(hasToken);
  const [isSessionExpired, setIsSessionExpired] = useState(false);

  const refreshUser = useCallback(async () => {
    if (!getStoredAccessToken()) {
      setUser(null);
      setHasToken(false);
      setIsLoadingUser(false);
      setIsSessionExpired(false);
      return null;
    }

    setIsLoadingUser(true);
    try {
      const currentUser = await apiClient.users.me();
      setUser(currentUser);
      setHasToken(true);
      setIsSessionExpired(false);
      return currentUser;
    } catch {
      clearAuthSession();
      setUser(null);
      setHasToken(false);
      setIsSessionExpired(true);
      return null;
    } finally {
      setIsLoadingUser(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    const handleSessionExpired = () => {
      clearAuthSession();
      setUser(null);
      setHasToken(false);
      setIsLoadingUser(false);
      setIsSessionExpired(true);
    };
    window.addEventListener("flipradar:session-expired", handleSessionExpired);
    return () =>
      window.removeEventListener(
        "flipradar:session-expired",
        handleSessionExpired,
      );
  }, []);

  const login = useCallback((session: AuthSession) => {
    storeAuthSession(session);
    setHasToken(true);
    setUser(session.user ?? null);
    setIsSessionExpired(false);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.auth.logout();
    } finally {
      setUser(null);
      setHasToken(false);
      setIsSessionExpired(false);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: hasToken,
      isLoadingUser,
      isSessionExpired,
      login,
      logout,
      refreshUser,
      user,
    }),
    [hasToken, isLoadingUser, isSessionExpired, login, logout, refreshUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
