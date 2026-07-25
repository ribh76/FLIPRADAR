import { Navigate, createBrowserRouter } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { ErrorLayout } from "./layouts/ErrorLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { AccountSettingsPage } from "./pages/AccountSettingsPage";
import { AnalyzePage } from "./pages/AnalyzePage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SetDetailPage } from "./pages/SetDetailPage";
import { SetsPage } from "./pages/SetsPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export const router = createBrowserRouter([
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
          { path: "/sets", element: <SetsPage /> },
          { path: "/sets/:setNumber", element: <SetDetailPage /> },
          { path: "/settings", element: <AccountSettingsPage /> },
        ],
      },
      { path: "*", element: <ErrorLayout /> },
    ],
  },
]);
