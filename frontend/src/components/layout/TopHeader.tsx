import { useAuth } from "@/features/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Search, LogOut, Activity } from "lucide-react";

export function TopHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-6 flex-shrink-0 z-10">
      <div className="flex items-center gap-4">
        {/* Global Command Menu Trigger */}
        <button className="flex items-center gap-2 text-sm text-muted-foreground bg-secondary/50 hover:bg-secondary border border-border/50 rounded-md px-3 py-1.5 transition-colors">
          <Search className="h-4 w-4" />
          <span>Search symbols, strategies...</span>
          <kbd className="ml-4 pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
            <span className="text-xs">⌘</span>K
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-secondary/30 px-2 py-1 rounded border border-border/50">
          <Activity className="h-3 w-3 text-emerald-500" />
          API: Connected
        </div>
        
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
