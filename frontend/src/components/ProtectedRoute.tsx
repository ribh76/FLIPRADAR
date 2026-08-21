import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isAuthenticated, isLoadingUser, isSessionExpired, user } = useAuth();

  if (isLoadingUser) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--color-background)] px-4 py-8 text-sm font-semibold text-[var(--color-text-inverse)]">
        Loading workspace...
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={isSessionExpired ? "/login?reason=session-expired" : "/login"}
        replace
        state={{ from: location }}
      />
    );
  }

  if (!user?.is_email_verified) {
    return <Navigate to="/verify-email?required=1" replace />;
  }

  return children;
}
