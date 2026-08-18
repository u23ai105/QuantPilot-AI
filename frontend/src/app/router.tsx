import { createBrowserRouter, Outlet } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "@/features/auth/components/ProtectedRoute";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { AppShell, PageContainer } from "@/components/layout/AppShell";

// Elegant Placeholders for Phase 7.2
const ResearchWorkspace = () => (
  <PageContainer title="AI Research Workspace" description="Your quantitative research environment.">
    <div className="flex items-center justify-center h-full border border-dashed border-border/50 rounded-lg bg-card/20">
      <p className="text-muted-foreground text-sm">Research capabilities will be enabled in Phase 7.3</p>
    </div>
  </PageContainer>
);

const Market = () => (
  <PageContainer title="Market Data" description="Explore OHLCV data and technical indicators.">
    <div className="flex items-center justify-center h-full border border-dashed border-border/50 rounded-lg bg-card/20">
      <p className="text-muted-foreground text-sm">Market analysis tools will be enabled in Phase 7.4</p>
    </div>
  </PageContainer>
);

const Strategies = () => (
  <PageContainer title="Strategies" description="Manage your declarative JSON trading strategies.">
    <div className="flex items-center justify-center h-full border border-dashed border-border/50 rounded-lg bg-card/20">
      <p className="text-muted-foreground text-sm">Strategy management will be enabled in Phase 7.5</p>
    </div>
  </PageContainer>
);

const Backtests = () => (
  <PageContainer title="Backtests" description="Submit backtests and review historical performance metrics.">
    <div className="flex items-center justify-center h-full border border-dashed border-border/50 rounded-lg bg-card/20">
      <p className="text-muted-foreground text-sm">Backtest engine UI will be enabled in Phase 7.5</p>
    </div>
  </PageContainer>
);

const Documents = () => (
  <PageContainer title="Documents" description="Upload and manage financial documents for AI retrieval.">
    <div className="flex items-center justify-center h-full border border-dashed border-border/50 rounded-lg bg-card/20">
      <p className="text-muted-foreground text-sm">Document ingestion will be enabled in Phase 7.6</p>
    </div>
  </PageContainer>
);

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
        element: <ResearchWorkspace />,
      },
      {
        path: "/market",
        element: <Market />,
      },
      {
        path: "/strategies",
        element: <Strategies />,
      },
      {
        path: "/backtests",
        element: <Backtests />,
      },
      {
        path: "/documents",
        element: <Documents />,
      },
    ],
  },
]);
