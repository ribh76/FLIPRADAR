import React from "react";
import ReactDOM from "react-dom/client";
import {
  Navigate,
  RouterProvider,
  createBrowserRouter,
} from "react-router-dom";
import App from "./App";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AnalyzePage } from "./pages/AnalyzePage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { AccountSettingsPage } from "./pages/AccountSettingsPage";
import { SetDetailPage } from "./pages/SetDetailPage";
import { SetsPage } from "./pages/SetsPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";
import "./styles.css";

const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <LoginPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  {
    element: (
      <ProtectedRoute>
        <App />
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
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
