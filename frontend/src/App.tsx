import { Outlet } from "react-router-dom";
import { AppShell } from "./components/AppShell";

export default function App() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
