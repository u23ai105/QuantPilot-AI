import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, TrendingUp, BarChart3 } from "lucide-react";
import { useState } from "react";

export function MarketPage() {
  const [symbol, setSymbol] = useState("");
  const [activeSymbol, setActiveSymbol] = useState("AAPL");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (symbol.trim()) {
      setActiveSymbol(symbol.toUpperCase());
    }
  };

  return (
    <PageContainer title="Market Data" description="Explore OHLCV data and technical indicators.">
      <div className="flex flex-col gap-6">
        <Card className="bg-background/50 border-border/50">
          <CardContent className="p-4 flex gap-4 items-center">
            <form onSubmit={handleSearch} className="flex flex-1 gap-2 max-w-md">
              <Input 
                value={symbol} 
                onChange={e => setSymbol(e.target.value)} 
                placeholder="Search symbol (e.g., AAPL)" 
                className="bg-background/50"
              />
              <Button type="submit" variant="secondary">
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="md:col-span-2 bg-background/50 border-border/50 h-96 flex flex-col">
            <CardHeader className="pb-2 border-b border-border/50">
              <CardTitle className="text-lg flex justify-between items-center">
                <span>{activeSymbol} - Price History</span>
                <span className="text-sm font-normal text-muted-foreground flex items-center gap-1">
                  <TrendingUp className="h-4 w-4 text-emerald-500" />
                  Live
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex items-center justify-center p-6">
              <div className="flex flex-col items-center text-muted-foreground gap-2">
                <BarChart3 className="h-8 w-8 opacity-20" />
                <p className="text-sm">Chart visualization module pending integration.</p>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="bg-background/50 border-border/50">
              <CardHeader className="pb-2 border-b border-border/50">
                <CardTitle className="text-sm">Key Indicators</CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">SMA (20)</span>
                  <span className="font-medium text-foreground">145.23</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">EMA (50)</span>
                  <span className="font-medium text-foreground">142.89</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">RSI (14)</span>
                  <span className="font-medium text-amber-500">58.4</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">MACD</span>
                  <span className="font-medium text-emerald-500">+1.24</span>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-background/50 border-border/50">
              <CardHeader className="pb-2 border-b border-border/50">
                <CardTitle className="text-sm">Latest OHLCV</CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Open</span>
                  <span className="font-medium text-foreground">150.10</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">High</span>
                  <span className="font-medium text-foreground">151.20</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Low</span>
                  <span className="font-medium text-foreground">148.90</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Close</span>
                  <span className="font-medium text-foreground">150.75</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Vol</span>
                  <span className="font-medium text-foreground">42.5M</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
