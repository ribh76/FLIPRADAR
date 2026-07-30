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
import { PortfolioPage } from "./features/portfolio/PortfolioPage";
import { HoldingDetailPage } from "./features/portfolio/HoldingDetailPage";
import { SetDetailPage } from "./features/sets/SetDetailPage";
import { SetsPage } from "./features/sets/SetsPage";
import { ShowcasePage } from "./features/showcase/ShowcasePage";
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
          { path: "/analyze", element: <AnalyzePage /> },
          { path: "/portfolio", element: <PortfolioPage /> },
          { path: "/portfolio/items/:itemId", element: <HoldingDetailPage /> },
          { path: "/sets", element: <SetsPage /> },
          { path: "/sets/:setNumber", element: <SetDetailPage /> },
          { path: "/showcase", element: <ShowcasePage /> },
          { path: "/settings", element: <AccountSettingsPage /> },
        ],
      },
      { path: "*", element: <ErrorLayout /> },
    ],
  },
];

export const router = createBrowserRouter(appRoutes);
