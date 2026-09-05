import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { backtestsApi } from "@/lib/api/resources";
import type { BacktestResponse } from "@/lib/api/resources";
import { CheckCircle2, ChevronDown, Clock, XCircle, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
// Recharts is a large dependency and only needed once a row is expanded, so it is code-split out
// of the main bundle rather than loaded on every page view.
const EquityCurveChart = lazy(() => import("../components/EquityCurveChart").then(m => ({ default: m.EquityCurveChart })));

function StatusIcon({ status }: { status: string }) {
  if (status === "COMPLETED") return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
  if (status === "FAILED") return <XCircle className="h-5 w-5 text-destructive" />;
  return <Clock className="h-5 w-5 text-amber-500 animate-pulse" />;
}

function BacktestRow({ bt }: { bt: BacktestResponse }) {
  const [expanded, setExpanded] = useState(false);
  const { data: result } = useQuery({
    queryKey: ["backtest-result", bt.id],
    queryFn: () => backtestsApi.getResults(bt.id),
    enabled: bt.status === "COMPLETED",
    retry: false,
  });

  // Only completed runs have a result payload, so only those can show a curve. Warmup bars sit
  // before start_date in the stored curve and the chart drops them, so count what will be plotted.
  const plotted = result ? result.equity_curve.filter(p => p.date.slice(0, 10) >= bt.start_date) : [];
  const canExpand = result != null && plotted.length > 0;

  return (
    <div className="hover:bg-secondary/20 transition-colors">
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <StatusIcon status={bt.status} />
          <div>
            <h4 className="font-medium text-sm text-foreground">Backtest #{bt.id}</h4>
            <p className="text-xs text-muted-foreground mt-0.5">
              Strategy {bt.strategy_id} • {bt.start_date} → {bt.end_date}
            </p>
            {bt.status === "FAILED" && bt.error_message && (
              <p className="flex items-start gap-1 text-xs text-destructive mt-1">
                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                <span>{bt.error_message}</span>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-8 text-right">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">Return</div>
            <div className={`text-sm font-medium ${result && result.total_return > 0 ? "text-emerald-500" : result ? "text-destructive" : "text-muted-foreground"}`}>
              {result ? `${(result.total_return * 100).toFixed(2)}%` : bt.status === "COMPLETED" ? "—" : bt.status}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">Sharpe</div>
            <div className="text-sm font-medium text-foreground">
              {result?.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">Drawdown</div>
            <div className="text-sm font-medium text-foreground">
              {result?.max_drawdown != null ? `${(result.max_drawdown * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          {canExpand ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(v => !v)}
              aria-expanded={expanded}
              aria-controls={`equity-curve-${bt.id}`}
            >
              <ChevronDown className={`h-4 w-4 mr-1 transition-transform ${expanded ? "rotate-180" : ""}`} aria-hidden="true" />
              {expanded ? "Hide chart" : "Show chart"}
            </Button>
          ) : (
            // Keep the metric columns aligned across rows that can't expand.
            <div className="w-[7.5rem]" aria-hidden="true" />
          )}
        </div>
      </div>
      {canExpand && expanded && (
        <div id={`equity-curve-${bt.id}`} className="border-t border-border/50 px-4 py-4">
          <div className="flex items-baseline justify-between mb-2">
            <h5 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Equity curve</h5>
            <span className="text-xs text-muted-foreground">
              {plotted.length} {plotted.length === 1 ? "bar" : "bars"} • {result.total_trades} {result.total_trades === 1 ? "trade" : "trades"}
            </span>
          </div>
          <Suspense
            fallback={
              <div className="flex h-64 items-center justify-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading chart...
              </div>
            }
          >
            <EquityCurveChart data={result.equity_curve} initialCapital={bt.initial_capital} startDate={bt.start_date} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

export function BacktestsPage() {
  // GET /backtests returns every run owned by the authenticated user, newest first, so the
  // history survives a page reload (the old sessionStorage id list did not).
  const { data: backtests, isLoading, error, refetch } = useQuery<BacktestResponse[]>({
    queryKey: ["backtests"],
    queryFn: () => backtestsApi.list(),
    // Keep polling only while something is still in flight.
    refetchInterval: query => {
      const rows = query.state.data;
      if (!rows) return false;
      return rows.some(bt => bt.status !== "COMPLETED" && bt.status !== "FAILED") ? 5000 : false;
    },
  });

  return (
    <PageContainer title="Backtests" description="Every backtest you've submitted, newest first.">
      <div className="flex justify-end mb-6">
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Card className="bg-background/50 border-border/50">
        <CardHeader className="border-b border-border/50 pb-4">
          <CardTitle className="text-sm font-medium">Execution History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm p-6">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm p-6">
              <AlertCircle className="h-4 w-4" /> Failed to load backtests
            </div>
          )}
          {!isLoading && (!backtests || backtests.length === 0) && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <p className="text-sm">No backtests yet.</p>
              <p className="text-xs mt-1">Go to <strong>Strategies</strong>, select a strategy, and click <em>Submit Backtest</em>.</p>
            </div>
          )}
          {backtests && backtests.length > 0 && (
            <div className="divide-y divide-border/50">
              {backtests.map(bt => <BacktestRow key={bt.id} bt={bt} />)}
            </div>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
