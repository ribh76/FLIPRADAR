import {
  Boxes,
  Calculator,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Palette,
  Search,
  Settings,
  Sun,
  UserRound,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { apiClient, getApiError } from "../services/apiClient";
import { useTheme } from "../theme/ThemeProvider";
import { Dropdown, DropdownItem, PageHeader } from "./ui";
import type { BreadcrumbItem } from "./ui";
import { Logo } from "./Logo";

const navItems = [
  {
    description: "Workspace overview and shortcuts.",
    icon: LayoutDashboard,
    label: "Dashboard",
    to: "/dashboard",
  },
  {
    description: "Decision support for LEGO set listings.",
    icon: Calculator,
    label: "Analyze",
    to: "/analyze",
  },
  {
    description: "Collection value, basis, and holdings.",
    icon: Boxes,
    label: "Portfolio",
    to: "/portfolio",
  },
  {
    description: "Set metadata and valuation lookup.",
    icon: Search,
    label: "Sets",
    to: "/sets",
  },
  {
    description: "Reusable component and brand examples.",
    icon: Palette,
    label: "Showcase",
    to: "/showcase",
  },
  {
    description: "Profile, email, sessions, and security.",
    icon: Settings,
    label: "Settings",
    to: "/settings",
  },
];

function getRouteMeta(pathname: string) {
  if (pathname.startsWith("/portfolio/items/")) {
    return {
      breadcrumbs: [
        { label: "Dashboard", to: "/dashboard" },
        { label: "Portfolio", to: "/portfolio" },
        { label: "Holding analytics" },
      ],
      description:
        "Value performance, market evidence, and risk for one holding.",
      eyebrow: "Portfolio intelligence",
      title: "Holding Analytics",
    };
  }

  if (pathname.startsWith("/sets/")) {
    return {
      breadcrumbs: [
        { label: "Dashboard", to: "/dashboard" },
        { label: "Sets", to: "/sets" },
        { label: "Detail" },
      ],
      description: "Metadata and current valuation for a single LEGO set.",
      eyebrow: "Set intelligence",
      title: "Set Detail Lookup",
    };
  }

  const current = navItems.find((item) => item.to === pathname) ?? navItems[0];
  const breadcrumbs: BreadcrumbItem[] =
    current.to === "/dashboard"
      ? [{ label: "Dashboard" }]
      : [{ label: "Dashboard", to: "/dashboard" }, { label: current.label }];

  return {
    breadcrumbs,
    description: current.description,
    eyebrow: "FlipRadar workspace",
    title:
      current.label === "Sets"
        ? "Set Detail Lookup"
        : current.label === "Analyze"
          ? "Analyze Set"
          : current.label,
  };
}

function navLinkClass(isActive: boolean) {
  return [
    "inline-flex min-h-11 items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm font-bold transition",
    isActive
      ? "bg-brand-accent text-brand-black"
      : "text-[rgba(255,247,237,0.78)] hover:bg-white/10 hover:text-white",
  ].join(" ");
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState("");
  const routeMeta = useMemo(
    () => getRouteMeta(location.pathname),
    [location.pathname],
  );

  async function handleLogout() {
    await logout();
    setIsMobileNavOpen(false);
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

  const navContent = (
    <>
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => setIsMobileNavOpen(false)}
            className={({ isActive }) => navLinkClass(isActive)}
          >
            <Icon size={18} aria-hidden="true" />
            {item.label}
          </NavLink>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-text)]">
      <a
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-[var(--radius-control)] focus:bg-brand-accent focus:px-4 focus:py-2 focus:text-sm focus:font-bold focus:text-brand-black"
        href="#main-content"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 hidden w-72 flex-col border-r border-white/10 bg-brand-black px-4 py-5 lg:flex">
        <Link className="mb-8" to="/dashboard" aria-label="FlipRadar dashboard">
          <Logo />
        </Link>
        <nav className="flex flex-1 flex-col gap-2" aria-label="Primary">
          {navContent}
        </nav>
        <div className="space-y-3 border-t border-white/10 pt-4">
          <button
            className="secondary-button w-full border-white/15 bg-white/5 text-[var(--color-text-inverse)] hover:bg-white/10"
            onClick={toggleTheme}
            type="button"
          >
            {theme === "dark" ? (
              <Sun size={17} aria-hidden="true" />
            ) : (
              <Moon size={17} aria-hidden="true" />
            )}
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
          <Dropdown
            label={
              <span className="inline-flex items-center gap-2">
                <UserRound size={17} aria-hidden="true" />
                {user?.display_name ?? user?.username ?? "Account"}
              </span>
            }
          >
            <DropdownItem onSelect={() => navigate("/settings")}>
              <Settings size={16} aria-hidden="true" />
              <span className="ml-2">Settings</span>
            </DropdownItem>
            <DropdownItem onSelect={() => void handleLogout()}>
              <LogOut size={16} aria-hidden="true" />
              <span className="ml-2">Logout</span>
            </DropdownItem>
          </Dropdown>
        </div>
      </aside>

      <header className="sticky top-0 z-30 border-b border-white/10 bg-brand-black/95 px-4 py-4 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-4">
          <Link to="/dashboard" aria-label="FlipRadar dashboard">
            <Logo compact />
          </Link>
          <div className="flex items-center gap-2">
            <button
              aria-label="Toggle theme"
              className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-control)] text-[var(--color-text-inverse)] transition hover:bg-white/10"
              onClick={toggleTheme}
              type="button"
            >
              {theme === "dark" ? (
                <Sun size={19} aria-hidden="true" />
              ) : (
                <Moon size={19} aria-hidden="true" />
              )}
            </button>
            <button
              aria-expanded={isMobileNavOpen}
              aria-label="Toggle navigation"
              className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-control)] text-[var(--color-text-inverse)] transition hover:bg-white/10"
              onClick={() => setIsMobileNavOpen((current) => !current)}
              type="button"
            >
              {isMobileNavOpen ? (
                <X size={20} aria-hidden="true" />
              ) : (
                <Menu size={20} aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
        {isMobileNavOpen ? (
          <nav className="mt-4 flex flex-col gap-2" aria-label="Mobile primary">
            {navContent}
            <button
              className="inline-flex min-h-11 items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm font-bold text-[rgba(255,247,237,0.78)] transition hover:bg-white/10 hover:text-white"
              onClick={() => void handleLogout()}
              type="button"
            >
              <LogOut size={18} aria-hidden="true" />
              Logout
            </button>
          </nav>
        ) : null}
      </header>

      <div className="lg:pl-72">
        {user && !user.is_email_verified ? (
          <section className="border-b border-[var(--color-accent)] bg-[rgba(73,252,226,0.12)] px-4 py-3 text-[var(--color-text-inverse)] lg:px-8">
            <div className="flex max-w-7xl flex-wrap items-center justify-between gap-3 text-sm font-semibold">
              <span>
                Verify your email address to finish securing your FlipRadar
                account.
              </span>
              <div className="flex flex-wrap items-center gap-3">
                {verificationMessage ? (
                  <span>{verificationMessage}</span>
                ) : null}
                <button
                  type="button"
                  onClick={resendVerification}
                  className="primary-button h-10"
                >
                  Resend email
                </button>
              </div>
            </div>
          </section>
        ) : null}

        <main
          className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8"
          id="main-content"
        >
          <PageHeader {...routeMeta} />
          {children}
        </main>
      </div>
    </div>
  );
}
