import { cn } from "@/lib/utils";
import { Link, useLocation } from "react-router-dom";
import { LineChart, LayoutDashboard, Settings, FileText, Database, Layers } from "lucide-react";

export function SidebarNavigation() {
  const location = useLocation();

  const links = [
    { name: "Research Workspace", path: "/", icon: LayoutDashboard },
    { name: "Market Data", path: "/market", icon: LineChart },
    { name: "Strategies", path: "/strategies", icon: Layers },
    { name: "Backtests", path: "/backtests", icon: Database },
    { name: "Documents", path: "/documents", icon: FileText },
  ];

  return (
    <aside className="w-64 border-r border-border/50 bg-background flex flex-col h-full flex-shrink-0">
      <div className="h-14 flex items-center px-6 border-b border-border/50">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-ai flex items-center justify-center">
            <div className="w-1.5 h-1.5 rounded-full bg-background" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            QuantPilot
          </span>
        </div>
      </div>
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4 px-2">
          Platform
        </div>
        {links.map((link) => {
          const isActive = location.pathname === link.path || (link.path !== "/" && location.pathname.startsWith(link.path));
          const Icon = link.icon;
          return (
            <Link
              key={link.path}
              to={link.path}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive 
                  ? "bg-secondary text-foreground" 
                  : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
              )}
            >
              <Icon className={cn("h-4 w-4", isActive ? "text-ai" : "text-muted-foreground")} />
              {link.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-border/50">
        <Link
          to="/settings"
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary/50 hover:text-foreground transition-colors"
        >
          <Settings className="h-4 w-4" />
          Settings
        </Link>
      </div>
    </aside>
  );
}
