import { Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-4 py-8">
      <Outlet />
    </main>
  );
}
