import { ReactNode } from "react";
import { SidebarNavigation } from "./SidebarNavigation";
import { TopHeader } from "./TopHeader";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <SidebarNavigation />
      <div className="flex flex-col flex-1 min-w-0">
        <TopHeader />
        <main className="flex-1 overflow-auto bg-background/50 relative">
          {children}
        </main>
      </div>
    </div>
  );
}

export function PageContainer({ children, title, description }: { children: ReactNode, title: string, description?: string }) {
  return (
    <div className="flex flex-col h-full w-full max-w-[1600px] mx-auto p-6 md:p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
      </header>
      <div className="flex-1 min-h-0">
        {children}
      </div>
    </div>
  );
}
