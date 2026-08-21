import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { strategiesApi, backtestsApi } from "@/lib/api/resources";
import type { StrategyResponse, BacktestResponse } from "@/lib/api/resources";
import { Plus, Code2, Play, Loader2, AlertCircle, ChevronRight } from "lucide-react";

const DEFAULT_STRATEGY_JSON = JSON.stringify({
  version: 1,
  entry: {
    conditions: [
      {
        indicator: "sma",
        params: { period: 50 },
        operator: "crosses_above",
        against: { indicator: "sma", params: { period: 200 } },
      },
    ],
    logic: "AND",
  },
  exit: {
    conditions: [
      {
        indicator: "sma",
        params: { period: 50 },
        operator: "crosses_below",
        against: { indicator: "sma", params: { period: 200 } },
      },
    ],
    logic: "AND",
  },
  position_sizing: { type: "fixed_fraction", value: 0.95 },
}, null, 2);

interface BacktestFormState {
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
}

export function StrategiesPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<StrategyResponse | null>(null);
  const [editorJson, setEditorJson] = useState(DEFAULT_STRATEGY_JSON);
  const [newName, setNewName] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [btForm, setBtForm] = useState<BacktestFormState>({
    symbol: "AAPL",
    start_date: "2021-01-01",
    end_date: "2023-12-31",
    initial_capital: "10000",
  });
  const [lastBacktest, setLastBacktest] = useState<BacktestResponse | null>(null);
  const [btError, setBtError] = useState<string | null>(null);

  const { data: strategies = [], isLoading, error } = useQuery({
    queryKey: ["strategies"],
    queryFn: () => strategiesApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: strategiesApi.create,
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      setSelected(s);
      setNewName("");
    },
  });

  const backtestMutation = useMutation({
    mutationFn: backtestsApi.create,
    onSuccess: (bt) => {
      setLastBacktest(bt);
      setBtError(null);
      // Persist ID for BacktestsPage
      const stored: number[] = (() => {
        try { return JSON.parse(sessionStorage.getItem("quantpilot_backtests") || "[]"); } catch { return []; }
      })();
      if (!stored.includes(bt.id)) {
        sessionStorage.setItem("quantpilot_backtests", JSON.stringify([...stored, bt.id]));
      }
    },
    onError: (e: Error) => {
      setBtError(e.message);
    },
  });

  const handleSelectStrategy = (s: StrategyResponse) => {
    setSelected(s);
    setEditorJson(JSON.stringify(s.rules_json, null, 2));
    setJsonError(null);
    setLastBacktest(null);
    setBtError(null);
  };

  const handleSaveNew = () => {
    if (!newName.trim()) return;
    let parsed;
    try {
      parsed = JSON.parse(editorJson);
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON — please fix syntax errors.");
      return;
    }
    createMutation.mutate({ name: newName.trim(), rules_json: parsed });
  };

  const handleRunBacktest = () => {
    if (!selected) return;
    backtestMutation.mutate({
      strategy_id: selected.id,
      symbol: btForm.symbol.toUpperCase(),
      start_date: btForm.start_date,
      end_date: btForm.end_date,
      initial_capital: parseFloat(btForm.initial_capital) || 10000,
    });
  };

  return (
    <PageContainer title="Strategies" description="Manage your declarative JSON trading strategies.">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: Strategy List ─────────────────────────────────────── */}
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-1">Your Strategies</h3>

          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm p-4">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm p-4">
              <AlertCircle className="h-4 w-4" /> Failed to load strategies
            </div>
          )}
          {!isLoading && strategies.length === 0 && (
            <p className="text-sm text-muted-foreground px-1">No strategies yet. Create one below.</p>
          )}

          {strategies.map((s) => (
            <Card
              key={s.id}
              onClick={() => handleSelectStrategy(s)}
              className={`bg-background/50 border-border/50 hover:border-ai/50 cursor-pointer transition-colors ${selected?.id === s.id ? "border-ai/70 bg-ai/5" : ""}`}
            >
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <h4 className="font-medium text-foreground text-sm">{s.name}</h4>
                  <p className="text-xs text-muted-foreground mt-0.5">v{s.version} • {new Date(s.created_at).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-muted-foreground" />
                  {selected?.id === s.id && <ChevronRight className="h-4 w-4 text-ai" />}
                </div>
              </CardContent>
            </Card>
          ))}

          {/* New Strategy */}
          <Card className="bg-background/50 border-border/50 border-dashed">
            <CardContent className="p-4 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">New Strategy</p>
              <Input
                placeholder="Strategy name..."
                value={newName}
                onChange={e => setNewName(e.target.value)}
                className="bg-background/50 text-sm h-8"
              />
              <Button
                size="sm"
                className="w-full bg-foreground text-background hover:bg-foreground/90"
                disabled={!newName.trim() || createMutation.isPending}
                onClick={handleSaveNew}
              >
                {createMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-2" /> : <Plus className="h-3 w-3 mr-2" />}
                Save Strategy
              </Button>
              {createMutation.isError && (
                <p className="text-xs text-destructive">{(createMutation.error as Error).message}</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Right: Editor + Backtest ─────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="bg-background/50 border-border/50 flex flex-col">
            <CardHeader className="pb-2 border-b border-border/50 flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {selected ? `${selected.name} — Rules JSON` : "Strategy Editor"}
              </CardTitle>
              {selected && (
                <span className="text-xs text-muted-foreground">Read-only view of stored rules</span>
              )}
            </CardHeader>
            <CardContent className="p-0">
              <textarea
                className="w-full min-h-[260px] bg-transparent border-0 p-4 font-mono text-sm text-foreground focus:ring-0 resize-none outline-none"
                value={selected ? JSON.stringify(selected.rules_json, null, 2) : editorJson}
                onChange={e => {
                  setEditorJson(e.target.value);
                  setJsonError(null);
                }}
                readOnly={!!selected}
                spellCheck={false}
              />
              {jsonError && <p className="px-4 pb-2 text-xs text-destructive">{jsonError}</p>}
            </CardContent>
          </Card>

          {/* Backtest Panel (only when a strategy is selected) */}
          {selected && (
            <Card className="bg-background/50 border-border/50">
              <CardHeader className="pb-2 border-b border-border/50">
                <CardTitle className="text-base">Run Backtest</CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Symbol</label>
                    <Input value={btForm.symbol} onChange={e => setBtForm(f => ({ ...f, symbol: e.target.value }))} className="bg-background/50 h-8 text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Capital ($)</label>
                    <Input value={btForm.initial_capital} onChange={e => setBtForm(f => ({ ...f, initial_capital: e.target.value }))} className="bg-background/50 h-8 text-sm" type="number" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">Start Date</label>
                    <Input value={btForm.start_date} onChange={e => setBtForm(f => ({ ...f, start_date: e.target.value }))} className="bg-background/50 h-8 text-sm" type="date" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">End Date</label>
                    <Input value={btForm.end_date} onChange={e => setBtForm(f => ({ ...f, end_date: e.target.value }))} className="bg-background/50 h-8 text-sm" type="date" />
                  </div>
                </div>

                <Button
                  className="bg-ai hover:bg-ai/90 text-background"
                  disabled={backtestMutation.isPending}
                  onClick={handleRunBacktest}
                >
                  {backtestMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                  Submit Backtest
                </Button>

                {btError && (
                  <div className="flex gap-2 text-destructive text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{btError}</span>
                  </div>
                )}

                {lastBacktest && (
                  <div className="rounded-lg bg-card border border-border/50 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Backtest Queued</p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div><span className="text-muted-foreground">ID:</span> <span className="font-medium">{lastBacktest.id}</span></div>
                      <div><span className="text-muted-foreground">Status:</span> <span className={`font-medium ${lastBacktest.status === "COMPLETED" ? "text-emerald-500" : "text-amber-500"}`}>{lastBacktest.status}</span></div>
                      <div><span className="text-muted-foreground">Symbol:</span> <span className="font-medium">{btForm.symbol.toUpperCase()}</span></div>
                      <div><span className="text-muted-foreground">Capital:</span> <span className="font-medium">${lastBacktest.initial_capital.toLocaleString()}</span></div>
                    </div>
                    <p className="text-xs text-muted-foreground">The backtest is being processed by Celery. Results will appear once the status is COMPLETED.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
