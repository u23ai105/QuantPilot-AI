import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { marketApi } from "@/lib/api/resources";
import { Search, TrendingUp, TrendingDown, AlertCircle, Loader2 } from "lucide-react";

export function MarketPage() {
  const [search, setSearch] = useState("AAPL");
  const [activeSymbol, setActiveSymbol] = useState("AAPL");

  const { isLoading: tickersLoading } = useQuery({
    queryKey: ["tickers"],
    queryFn: () => marketApi.getTickers(),
  });

  const { data: ohlcv, isLoading: ohlcvLoading, error: ohlcvError } = useQuery({
    queryKey: ["ohlcv", activeSymbol],
    queryFn: () => marketApi.getTickerData(activeSymbol),
    enabled: !!activeSymbol,
    retry: false,
  });

  const { data: sma } = useQuery({
    queryKey: ["indicator", activeSymbol, "sma"],
    queryFn: () => marketApi.getIndicators(activeSymbol, "sma", { period: "20" }),
    enabled: !!activeSymbol,
    retry: false,
  });

  const { data: rsi } = useQuery({
    queryKey: ["indicator", activeSymbol, "rsi"],
    queryFn: () => marketApi.getIndicators(activeSymbol, "rsi", { period: "14" }),
    enabled: !!activeSymbol,
    retry: false,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) setActiveSymbol(search.trim().toUpperCase());
  };

  const latestOhlcv = ohlcv && ohlcv.length > 0 ? ohlcv[ohlcv.length - 1] : null;
  const prevOhlcv = ohlcv && ohlcv.length > 1 ? ohlcv[ohlcv.length - 2] : null;
  const isUp = latestOhlcv && prevOhlcv ? latestOhlcv.close >= prevOhlcv.close : true;

  const latestSma = sma && sma.length > 0 ? sma[sma.length - 1].value : null;
  const latestRsi = rsi && rsi.length > 0 ? rsi[rsi.length - 1].value : null;

  return (
    <PageContainer title="Market Data" description="Explore OHLCV data and technical indicators.">
      <div className="flex gap-4 mb-6">
        <form onSubmit={handleSearch} className="relative w-72 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search ticker (e.g. MSFT)..."
              className="pl-9 bg-background/50"
            />
          </div>
          <button type="submit" className="hidden" />
        </form>
        {tickersLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground mt-3" />}
      </div>

      {ohlcvError && (
        <div className="mb-6 flex items-center gap-2 text-destructive text-sm bg-destructive/10 rounded-lg p-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Failed to load market data. Make sure "{activeSymbol}" has been ingested in the backend.
        </div>
      )}

      {/* Hero Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Latest Close</p>
              {ohlcvLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold">${latestOhlcv?.close.toFixed(2) || "—"}</span>
                  {latestOhlcv && prevOhlcv && (
                    <span className={`flex items-center text-xs font-medium ${isUp ? "text-emerald-500" : "text-destructive"}`}>
                      {isUp ? <TrendingUp className="h-3 w-3 mr-0.5" /> : <TrendingDown className="h-3 w-3 mr-0.5" />}
                      {Math.abs(((latestOhlcv.close - prevOhlcv.close) / prevOhlcv.close) * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Volume</p>
            {ohlcvLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestOhlcv?.volume.toLocaleString() || "—"}</span>
            )}
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">SMA (20)</p>
            {sma === undefined ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestSma ? latestSma.toFixed(2) : "—"}</span>
            )}
          </CardContent>
        </Card>

        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">RSI (14)</p>
            {rsi === undefined ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="text-lg font-medium">{latestRsi ? latestRsi.toFixed(2) : "—"}</span>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Data Table */}
      <Card className="bg-background/50 border-border/50">
        <CardHeader className="border-b border-border/50 pb-4">
          <CardTitle className="text-sm font-medium">{activeSymbol} OHLCV (Latest 10 Days)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-muted-foreground">
                  <th className="text-left font-medium p-4 py-3">Date</th>
                  <th className="text-right font-medium p-4 py-3">Open</th>
                  <th className="text-right font-medium p-4 py-3">High</th>
                  <th className="text-right font-medium p-4 py-3">Low</th>
                  <th className="text-right font-medium p-4 py-3">Close</th>
                  <th className="text-right font-medium p-4 py-3">Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {ohlcvLoading && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></td>
                  </tr>
                )}
                {!ohlcvLoading && (!ohlcv || ohlcv.length === 0) && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">No data available.</td>
                  </tr>
                )}
                {ohlcv && ohlcv.slice(-10).reverse().map((row, i) => (
                  <tr key={i} className="hover:bg-secondary/20 transition-colors">
                    <td className="p-4 py-3 text-muted-foreground">{row.date}</td>
                    <td className="p-4 py-3 text-right">${row.open.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right">${row.high.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right">${row.low.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right font-medium">${row.close.toFixed(2)}</td>
                    <td className="p-4 py-3 text-right text-muted-foreground">{row.volume.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
