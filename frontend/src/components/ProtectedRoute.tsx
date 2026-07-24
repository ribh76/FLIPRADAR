import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getStoredAccessToken } from "../api/client";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();

  if (!getStoredAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
