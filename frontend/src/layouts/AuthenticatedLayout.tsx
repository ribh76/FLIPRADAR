import { useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";

export function AuthenticatedLayout() {
  const navigate = useNavigate();

  useEffect(() => {
    const redirectUnauthorized = () =>
      navigate("/unauthorized", { replace: true });
    window.addEventListener("flipradar:unauthorized", redirectUnauthorized);
    return () =>
      window.removeEventListener(
        "flipradar:unauthorized",
        redirectUnauthorized,
      );
  }, [navigate]);

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
