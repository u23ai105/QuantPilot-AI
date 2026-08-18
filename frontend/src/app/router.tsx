import { createBrowserRouter, Outlet } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "@/features/auth/components/ProtectedRoute";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { AppShell } from "@/components/layout/AppShell";
import { ResearchPage } from "@/features/research/pages/ResearchPage";
import { MarketPage } from "@/features/market/pages/MarketPage";
import { StrategiesPage } from "@/features/strategies/pages/StrategiesPage";
import { BacktestsPage } from "@/features/backtests/pages/BacktestsPage";
import { DocumentsPage } from "@/features/documents/pages/DocumentsPage";

const AuthenticatedLayout = () => {
  return (
    <ProtectedRoute>
      <AppShell>
        <Outlet />
      </AppShell>
    </ProtectedRoute>
  );
};

export const router = createBrowserRouter([
  {
    element: <PublicRoute />,
    children: [
      {
        path: "/login",
        element: <LoginPage />,
      },
    ],
  },
  {
    element: <AuthenticatedLayout />,
    children: [
      {
        path: "/",
        element: <ResearchPage />,
      },
      {
        path: "/market",
        element: <MarketPage />,
      },
      {
        path: "/strategies",
        element: <StrategiesPage />,
      },
      {
        path: "/backtests",
        element: <BacktestsPage />,
      },
      {
        path: "/documents",
        element: <DocumentsPage />,
      },
    ],
  },
]);
