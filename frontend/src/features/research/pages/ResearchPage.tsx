import { useState } from "react";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Send, Bot, User } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function ResearchPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: "1", role: "assistant", content: "Hello! I am your QuantPilot AI research assistant. How can I help you analyze the market today?" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;
    
    const newMsg: Message = { id: Date.now().toString(), role: "user", content: input };
    setMessages(prev => [...prev, newMsg]);
    setInput("");
    setIsLoading(true);

    // Mock API call
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I am processing your request. Integration with the LangGraph agent will be connected here."
      }]);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <PageContainer title="AI Research Workspace" description="Interact with your quantitative research assistant.">
      <div className="flex h-full gap-6">
        <Card className="flex-1 flex flex-col h-[calc(100vh-12rem)] bg-background/50 border-border/50">
          <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map(m => (
              <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "assistant" && (
                  <div className="w-8 h-8 rounded-full bg-ai flex items-center justify-center shrink-0">
                    <Bot className="h-4 w-4 text-background" />
                  </div>
                )}
                <div className={`max-w-[80%] rounded-lg p-3 text-sm ${m.role === "user" ? "bg-secondary text-foreground" : "bg-card border border-border/50 text-foreground"}`}>
                  {m.content}
                </div>
                {m.role === "user" && (
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-ai flex items-center justify-center shrink-0">
                  <Bot className="h-4 w-4 text-background" />
                </div>
                <div className="max-w-[80%] rounded-lg p-3 text-sm bg-card border border-border/50 text-muted-foreground">
                  Thinking...
                </div>
              </div>
            )}
          </CardContent>
          <div className="p-4 border-t border-border/50 bg-card/50">
            <form onSubmit={e => { e.preventDefault(); handleSend(); }} className="flex gap-2">
              <Input 
                value={input} 
                onChange={e => setInput(e.target.value)} 
                placeholder="Ask about AAPL's 200-day SMA, or search 10-K documents..." 
                className="bg-background/50"
                disabled={isLoading}
              />
              <Button type="submit" disabled={isLoading || !input.trim()} className="bg-ai hover:bg-ai/90 text-background">
                <Send className="h-4 w-4" />
                <span className="sr-only">Send</span>
              </Button>
            </form>
          </div>
        </Card>
        <div className="w-80 hidden lg:flex flex-col gap-4">
          <Card className="flex-1 bg-background/50 border-border/50 p-4">
            <h3 className="font-medium text-sm text-foreground mb-4">Context & Tools</h3>
            <div className="text-xs text-muted-foreground">
              Tool execution and retrieved context will appear here during processing.
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
