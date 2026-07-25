import {
  BarChart3,
  Boxes,
  Calculator,
  LayoutDashboard,
  LogOut,
  Search,
  Settings,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { apiClient, getApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { Logo } from "./Logo";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/analyze", label: "Analyze", icon: Calculator },
  { to: "/portfolio", label: "Portfolio", icon: Boxes },
  { to: "/sets", label: "Sets", icon: Search },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [verificationMessage, setVerificationMessage] = useState("");

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  async function resendVerification() {
    setVerificationMessage("");
    try {
      const response = await apiClient.auth.resendVerification();
      setVerificationMessage(response.message);
    } catch (error) {
      setVerificationMessage(getApiError(error));
    }
  }

  return (
    <div className="min-h-screen bg-navy-950 text-slate-950">
      <header className="border-b border-white/10 bg-navy-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link to="/dashboard" aria-label="FlipRadar dashboard">
            <Logo />
          </Link>
          <nav className="flex flex-wrap items-center gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    [
                      "inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-semibold transition",
                      isActive
                        ? "bg-white text-navy-950"
                        : "text-blue-100 hover:bg-white/10 hover:text-white",
                    ].join(" ")
                  }
                >
                  <Icon size={17} aria-hidden="true" />
                  {item.label}
                </NavLink>
              );
            })}
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-semibold text-blue-100 transition hover:bg-white/10 hover:text-white"
            >
              <LogOut size={17} aria-hidden="true" />
              Logout
            </button>
          </nav>
        </div>
      </header>
      {user && !user.is_email_verified ? (
        <section className="border-b border-blue-200 bg-blue-50 px-4 py-3 text-blue-950">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 text-sm font-medium sm:px-6 lg:px-8">
            <span>
              Verify your email address to finish securing your FlipRadar
              account.
            </span>
            <div className="flex flex-wrap items-center gap-3">
              {verificationMessage ? <span>{verificationMessage}</span> : null}
              <button
                type="button"
                onClick={resendVerification}
                className="rounded-md bg-blue-700 px-3 py-2 text-sm font-bold text-white"
              >
                Resend email
              </button>
            </div>
          </div>
        </section>
      ) : null}
      <main className="mx-auto min-h-[calc(100vh-73px)] max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-7 flex items-center gap-3 text-blue-100">
          <BarChart3 size={18} aria-hidden="true" />
          <span className="text-sm font-semibold">
            Collector valuation workspace
          </span>
        </div>
        {children}
      </main>
    </div>
  );
}
