import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, CheckCircle2, Clock } from "lucide-react";

export function BacktestsPage() {
  const mockBacktests = [
    { id: "bt_1", strategy: "SMA Crossover", symbol: "AAPL", status: "COMPLETED", return: "+12.4%", sharpe: "1.2" },
    { id: "bt_2", strategy: "Mean Reversion", symbol: "TSLA", status: "RUNNING", return: "-", sharpe: "-" },
  ];

  return (
    <PageContainer title="Backtests" description="Submit backtests and review historical performance metrics.">
      <div className="flex justify-end mb-6">
        <Button className="bg-foreground text-background hover:bg-foreground/90">
          <Play className="h-4 w-4 mr-2" />
          New Backtest
        </Button>
      </div>

      <Card className="bg-background/50 border-border/50">
        <CardHeader className="border-b border-border/50 pb-4">
          <CardTitle className="text-sm font-medium">Recent Executions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border/50">
            {mockBacktests.map(bt => (
              <div key={bt.id} className="p-4 flex items-center justify-between hover:bg-secondary/20 transition-colors">
                <div className="flex items-center gap-4">
                  {bt.status === "COMPLETED" ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  ) : (
                    <Clock className="h-5 w-5 text-amber-500 animate-pulse" />
                  )}
                  <div>
                    <h4 className="font-medium text-sm text-foreground">{bt.strategy}</h4>
                    <p className="text-xs text-muted-foreground mt-0.5">{bt.symbol} • {bt.id}</p>
                  </div>
                </div>
                <div className="flex gap-8 text-right">
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">Return</div>
                    <div className={`text-sm font-medium ${bt.return.startsWith('+') ? 'text-emerald-500' : 'text-foreground'}`}>
                      {bt.return}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">Sharpe</div>
                    <div className="text-sm font-medium text-foreground">{bt.sharpe}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
