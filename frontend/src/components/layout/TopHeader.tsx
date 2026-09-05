import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { healthApi } from "@/lib/api/resources";
import { LogOut, Activity } from "lucide-react";

/** Live API status derived from `GET /ready`, which reports DB and Redis health. */
function ApiStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ready"],
    queryFn: () => healthApi.ready(),
    refetchInterval: 30_000,
    retry: false,
  });

  let label: string;
  let dotClass: string;
  if (isLoading) {
    label = "API: Checking...";
    dotClass = "text-muted-foreground animate-pulse";
  } else if (isError || !data) {
    label = "API: Unreachable";
    dotClass = "text-destructive";
  } else if (data.status === "ok") {
    label = "API: Connected";
    dotClass = "text-emerald-500";
  } else {
    // /ready answered but a dependency is down — name it rather than claiming "Connected".
    const down = [data.db !== "ok" && "DB", data.redis !== "ok" && "Redis"].filter(Boolean).join(" + ");
    label = `API: Degraded${down ? ` (${down} down)` : ""}`;
    dotClass = "text-amber-500";
  }

  return (
    <div
      className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-secondary/30 px-2 py-1 rounded border border-border/50"
      role="status"
      aria-live="polite"
    >
      <Activity className={`h-3 w-3 ${dotClass}`} aria-hidden="true" />
      {label}
    </div>
  );
}

export function TopHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-6 flex-shrink-0 z-10">
      <div className="flex items-center gap-4" />

      <div className="flex items-center gap-4">
        <ApiStatus />

        <div className="h-4 w-px bg-border/50" />

        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-foreground">{user?.email}</span>
          <Button variant="ghost" size="icon" onClick={logout} className="h-8 w-8 text-muted-foreground hover:text-foreground">
            <LogOut className="h-4 w-4" />
            <span className="sr-only">Log out</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
