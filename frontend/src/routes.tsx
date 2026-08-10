import {
  Navigate,
  createBrowserRouter,
  type RouteObject,
} from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccountSettingsPage } from "./features/account/AccountSettingsPage";
import { AnalyzePage } from "./features/analyze/AnalyzePage";
import { LoginPage } from "./features/auth/LoginPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { VerifyEmailPage } from "./features/auth/VerifyEmailPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DealsPage } from "./features/deals/DealsPage";
import { ListingEvaluatorPage } from "./features/listings/ListingEvaluatorPage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { PortfolioPage } from "./features/portfolio/PortfolioPage";
import { AnalyzePortfolioPage } from "./features/portfolio/AnalyzePortfolioPage";
import { HoldingDetailPage } from "./features/portfolio/HoldingDetailPage";
import { SetDetailPage } from "./features/sets/SetDetailPage";
import { SetsPage } from "./features/sets/SetsPage";
import { ShowcasePage } from "./features/showcase/ShowcasePage";
import { WatchlistPage } from "./features/watchlist/WatchlistPage";
import { NotFoundPage } from "./features/errors/NotFoundPage";
import { UnauthorizedPage } from "./features/errors/UnauthorizedPage";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { ErrorLayout } from "./layouts/ErrorLayout";
import { PublicLayout } from "./layouts/PublicLayout";

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
          { path: "/deals", element: <DealsPage /> },
          { path: "/analyze", element: <AnalyzePage /> },
          { path: "/listing-evaluator", element: <ListingEvaluatorPage /> },
          { path: "/portfolio", element: <PortfolioPage /> },
          { path: "/portfolio/analyze", element: <AnalyzePortfolioPage /> },
          { path: "/watchlist", element: <WatchlistPage /> },
          { path: "/notifications", element: <NotificationsPage /> },
          { path: "/portfolio/items/:itemId", element: <HoldingDetailPage /> },
          { path: "/sets", element: <SetsPage /> },
          { path: "/sets/:setNumber", element: <SetDetailPage /> },
          { path: "/showcase", element: <ShowcasePage /> },
          { path: "/settings", element: <AccountSettingsPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);
