import { useQuery } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { backtestsApi } from "@/lib/api/resources";
import type { BacktestResponse } from "@/lib/api/resources";
import { CheckCircle2, Clock, XCircle, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

function StatusIcon({ status }: { status: string }) {
  if (status === "COMPLETED") return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
  if (status === "FAILED") return <XCircle className="h-5 w-5 text-destructive" />;
  return <Clock className="h-5 w-5 text-amber-500 animate-pulse" />;
}

function BacktestRow({ bt }: { bt: BacktestResponse }) {
  const { data: result } = useQuery({
    queryKey: ["backtest-result", bt.id],
    queryFn: () => backtestsApi.getResults(bt.id),
    enabled: bt.status === "COMPLETED",
    retry: false,
  });

  return (
    <div className="p-4 flex items-center justify-between hover:bg-secondary/20 transition-colors">
      <div className="flex items-center gap-4">
        <StatusIcon status={bt.status} />
        <div>
          <h4 className="font-medium text-sm text-foreground">Backtest #{bt.id}</h4>
          <p className="text-xs text-muted-foreground mt-0.5">
            Strategy {bt.strategy_id} • {bt.start_date} → {bt.end_date}
          </p>
        </div>
      </div>
      <div className="flex gap-8 text-right">
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
      </div>
    </div>
  );
}

export function BacktestsPage() {
  // There's no list-all-backtests endpoint, so we note that clearly.
  // Backtests are submitted from the Strategies page and tracked here by ID from sessionStorage.
  const storedIds: number[] = (() => {
    try { return JSON.parse(sessionStorage.getItem("quantpilot_backtests") || "[]"); } catch { return []; }
  })();

  const { data: backtests, isLoading, error, refetch } = useQuery<BacktestResponse[]>({
    queryKey: ["backtests", storedIds],
    queryFn: async () => {
      if (storedIds.length === 0) return [];
      const results = await Promise.allSettled(storedIds.map(id => backtestsApi.get(id)));
      return results
        .filter(r => r.status === "fulfilled")
        .map(r => (r as PromiseFulfilledResult<BacktestResponse>).value);
    },
    refetchInterval: storedIds.length > 0 ? 5000 : false,
  });

  return (
    <PageContainer title="Backtests" description="Submit backtests from the Strategies page and monitor results here.">
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
