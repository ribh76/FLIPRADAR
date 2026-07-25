import { Outlet } from "react-router-dom";
import { AppShell } from "../components/AppShell";

export function AuthenticatedLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
