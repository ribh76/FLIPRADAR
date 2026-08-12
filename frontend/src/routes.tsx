import { lazy, Suspense, type ReactNode } from "react";
import {
  Navigate,
  createBrowserRouter,
  type RouteObject,
} from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./features/auth/LoginPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { VerifyEmailPage } from "./features/auth/VerifyEmailPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { NotFoundPage } from "./features/errors/NotFoundPage";
import { UnauthorizedPage } from "./features/errors/UnauthorizedPage";
import { AnalyzePortfolioPage } from "./features/portfolio/AnalyzePortfolioPage";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { ErrorLayout } from "./layouts/ErrorLayout";
import { PublicLayout } from "./layouts/PublicLayout";

const AccountSettingsPage = lazy(async () => ({
  default: (await import("./features/account/AccountSettingsPage"))
    .AccountSettingsPage,
}));
const AnalyzePage = lazy(async () => ({
  default: (await import("./features/analyze/AnalyzePage")).AnalyzePage,
}));
const DealsPage = lazy(async () => ({
  default: (await import("./features/deals/DealsPage")).DealsPage,
}));
const ListingEvaluatorPage = lazy(async () => ({
  default: (await import("./features/listings/ListingEvaluatorPage"))
    .ListingEvaluatorPage,
}));
const NotificationsPage = lazy(async () => ({
  default: (await import("./features/notifications/NotificationsPage"))
    .NotificationsPage,
}));
const PortfolioPage = lazy(async () => ({
  default: (await import("./features/portfolio/PortfolioPage")).PortfolioPage,
}));
const PartSearchPage = lazy(async () => ({
  default: (await import("./features/parts/PartSearchPage")).PartSearchPage,
}));
const HoldingDetailPage = lazy(async () => ({
  default: (await import("./features/portfolio/HoldingDetailPage"))
    .HoldingDetailPage,
}));
const SetDetailPage = lazy(async () => ({
  default: (await import("./features/sets/SetDetailPage")).SetDetailPage,
}));
const SetsPage = lazy(async () => ({
  default: (await import("./features/sets/SetsPage")).SetsPage,
}));
const ShowcasePage = lazy(async () => ({
  default: (await import("./features/showcase/ShowcasePage")).ShowcasePage,
}));
const WatchlistPage = lazy(async () => ({
  default: (await import("./features/watchlist/WatchlistPage")).WatchlistPage,
}));

function lazyPage(page: ReactNode) {
  return (
    <Suspense fallback={<div className="page-card">Loading page…</div>}>
      {page}
    </Suspense>
  );
}

export const appRoutes: RouteObject[] = [
  {
    errorElement: <ErrorLayout />,
    children: [
      { path: "/", element: <Navigate to="/login" replace /> },
      {
        element: <PublicLayout />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/register", element: <LoginPage /> },
          { path: "/reset-password", element: <ResetPasswordPage /> },
          { path: "/verify-email", element: <VerifyEmailPage /> },
          { path: "/unauthorized", element: <UnauthorizedPage /> },
        ],
      },
      {
        element: (
          <ProtectedRoute>
            <AuthenticatedLayout />
          </ProtectedRoute>
        ),
        children: [
          { path: "/dashboard", element: <DashboardPage /> },
          { path: "/deals", element: lazyPage(<DealsPage />) },
          { path: "/analyze", element: lazyPage(<AnalyzePage />) },
          {
            path: "/listing-evaluator",
            element: lazyPage(<ListingEvaluatorPage />),
          },
          { path: "/portfolio", element: lazyPage(<PortfolioPage />) },
          { path: "/portfolio/analyze", element: <AnalyzePortfolioPage /> },
          { path: "/watchlist", element: lazyPage(<WatchlistPage />) },
          { path: "/notifications", element: lazyPage(<NotificationsPage />) },
          {
            path: "/portfolio/items/:itemId",
            element: lazyPage(<HoldingDetailPage />),
          },
          { path: "/sets", element: lazyPage(<SetsPage />) },
          { path: "/parts", element: lazyPage(<PartSearchPage />) },
          { path: "/sets/:setNumber", element: lazyPage(<SetDetailPage />) },
          { path: "/showcase", element: lazyPage(<ShowcasePage />) },
          { path: "/settings", element: lazyPage(<AccountSettingsPage />) },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);
