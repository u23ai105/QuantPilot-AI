import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Code2, Play } from "lucide-react";

export function StrategiesPage() {
  const mockStrategies = [
    { id: 1, name: "SMA Crossover", version: "1.0", updated: "2023-10-15" },
    { id: 2, name: "Mean Reversion Base", version: "2.1", updated: "2023-10-20" },
  ];

  return (
    <PageContainer title="Strategies" description="Manage your declarative JSON trading strategies.">
      <div className="flex justify-end mb-6">
        <Button className="bg-foreground text-background hover:bg-foreground/90">
          <Plus className="h-4 w-4 mr-2" />
          New Strategy
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-sm font-medium text-muted-foreground px-1">Your Strategies</h3>
          {mockStrategies.map(s => (
            <Card key={s.id} className="bg-background/50 border-border/50 hover:border-ai/50 cursor-pointer transition-colors">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <h4 className="font-medium text-foreground text-sm">{s.name}</h4>
                  <p className="text-xs text-muted-foreground mt-1">v{s.version} • {s.updated}</p>
                </div>
                <Code2 className="h-4 w-4 text-muted-foreground" />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="lg:col-span-2">
          <Card className="bg-background/50 border-border/50 h-full min-h-[400px] flex flex-col">
            <CardHeader className="pb-2 border-b border-border/50 flex flex-row items-center justify-between">
              <CardTitle className="text-lg">SMA Crossover JSON Editor</CardTitle>
              <Button size="sm" variant="secondary">
                <Play className="h-3 w-3 mr-2" />
                Run Backtest
              </Button>
            </CardHeader>
            <CardContent className="p-0 flex-1">
              <textarea 
                className="w-full h-full min-h-[300px] bg-transparent border-0 p-4 font-mono text-sm text-foreground focus:ring-0 resize-none outline-none"
                defaultValue={JSON.stringify({
                  "name": "SMA Crossover",
                  "type": "crossover",
                  "parameters": {
                    "fast_period": 50,
                    "slow_period": 200,
                    "indicator": "SMA"
                  }
                }, null, 2)}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
