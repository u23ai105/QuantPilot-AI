import { useState, useEffect, useRef, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Send, Bot, User, Wrench, AlertCircle, Loader2 } from "lucide-react";
import { conversationsApi } from "@/lib/api/resources";

interface ClientMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  isError?: boolean;
}

interface ToolEvent {
  tool: string;
  summary?: string;
}

interface ActiveStream {
  userMsg: string;
  asstMsg: string;
  isStreaming: boolean;
  isError: boolean;
}

export function ResearchPage() {
  const queryClient = useQueryClient();
  const [activeConvId, setActiveConvId] = useState<string | null>(() => 
    sessionStorage.getItem("quantpilot_conv_id")
  );

  // Fetch historical messages if we have a conversation ID
  const { data: historyData, isLoading: isLoadingHistory, error: historyError } = useQuery({
    queryKey: ["conversation", activeConvId],
    queryFn: async () => {
      if (!activeConvId) return null;
      try {
        return await conversationsApi.getMessages(activeConvId);
      } catch (err: any) {
        // If conversation is missing or unauthorized, nuke it
        if (err.status === 404 || err.status === 401 || err.status === 403) {
          sessionStorage.removeItem("quantpilot_conv_id");
          setActiveConvId(null);
        }
        throw err;
      }
    },
    enabled: !!activeConvId,
    retry: false
  });

  const [activeStream, setActiveStream] = useState<ActiveStream | null>(null);
  const [toolsRun, setToolsRun] = useState<ToolEvent[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Clean up ongoing fetch on unmount to prevent detached state updates, 
  // without canceling the backend's internal work.
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const combinedMessages = useMemo(() => {
    // Ensure DB roles ("USER" / "ASSISTANT") are mapped strictly to UI types
    const msgs: ClientMessage[] = (historyData?.messages || []).map(m => ({
      id: m.id.toString(),
      role: m.role.toLowerCase() as "user" | "assistant",
      content: m.content
    }));

    // Append optimistic active stream
    if (activeStream) {
      msgs.push({ id: "optimistic-user", role: "user", content: activeStream.userMsg });
      msgs.push({ 
        id: "optimistic-asst", 
        role: "assistant", 
        content: activeStream.asstMsg, 
        isStreaming: activeStream.isStreaming, 
        isError: activeStream.isError 
      });
    }

    return msgs;
  }, [historyData, activeStream]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [combinedMessages, toolsRun]);

  const handleSend = async () => {
    if (!input.trim() || activeStream?.isStreaming) return;
    
    let convId = activeConvId;
    const userMsgContent = input.trim();
    
    // Setup Optimistic UI
    setInput("");
    setActiveStream({
      userMsg: userMsgContent,
      asstMsg: "",
      isStreaming: true,
      isError: false
    });
    setToolsRun([]);

    abortControllerRef.current = new AbortController();

    try {
      // Create conversation dynamically on first message to avoid StrictMode empty-conversation spam
      if (!convId) {
        const conv = await conversationsApi.create("Research Query");
        convId = conv.id;
        sessionStorage.setItem("quantpilot_conv_id", convId);
        setActiveConvId(convId);
      }

      const token = sessionStorage.getItem("access_token");
      const url = `${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"}/conversations/${convId}/messages`;
      
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content: userMsgContent }),
        signal: abortControllerRef.current.signal
      });

      if (!res.ok) {
        throw new Error(`API Error: ${res.statusText}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream available");
      
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const eventMatch = block.match(/event: (.*)\n/);
          const dataMatch = block.match(/data: (.*)/);
          
          if (eventMatch && dataMatch) {
            const event = eventMatch[1];
            try {
              const data = JSON.parse(dataMatch[1]);
              
              if (event === "token") {
                setActiveStream(prev => prev ? { ...prev, asstMsg: prev.asstMsg + data.content } : null);
              } else if (event === "tool_start") {
                setToolsRun(prev => [...prev, { tool: data.tool }]);
              } else if (event === "tool_end") {
                setToolsRun(prev => prev.map(t => 
                  t.tool === data.tool && !t.summary ? { ...t, summary: data.result_summary } : t
                ));
              }
            } catch (e) {
              // Ignore malformed JSON chunks gracefully
            }
          }
        }
      }

      // 1. Refetch exact DB state
      await queryClient.invalidateQueries({ queryKey: ["conversation", convId] });
      // 2. Clear local optimistic state only AFTER refetch finishes to avoid flicker/duplicates
      setActiveStream(null);

    } catch (e: any) {
      if (e.name === 'AbortError') {
        console.log('Fetch aborted on unmount');
        return;
      }
      console.error("Chat error:", e);
      setActiveStream(prev => prev ? { 
        ...prev, 
        asstMsg: prev.asstMsg + `\n\n[System Error: ${e.message}]`, 
        isStreaming: false, 
        isError: true 
      } : null);
    } finally {
      abortControllerRef.current = null;
    }
  };

  const showInitialGreeting = combinedMessages.length === 0 && !isLoadingHistory;

  return (
    <PageContainer title="AI Research Workspace" description="Interact with your LangGraph quantitative research assistant.">
      <div className="flex h-full gap-6">
        <Card className="flex-1 flex flex-col h-[calc(100vh-12rem)] bg-background/50 border-border/50">
          <CardContent ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            
            {isLoadingHistory && (
              <div className="flex justify-center p-8 text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            )}
            
            {historyError && !activeConvId && (
              <div className="flex justify-center p-8 text-destructive text-sm">
                <AlertCircle className="h-4 w-4 mr-2" /> Could not load previous conversation. Starting a new one.
              </div>
            )}

            {showInitialGreeting && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-ai flex items-center justify-center shrink-0">
                  <Bot className="h-4 w-4 text-background" />
                </div>
                <div className="max-w-[80%] rounded-lg p-3 text-sm whitespace-pre-wrap bg-card border border-border/50 text-foreground">
                  Hello! I am your QuantPilot AI research assistant. I can fetch market data, analyze historical prices, calculate technical indicators, or search through uploaded financial documents. How can I help you today?
                </div>
              </div>
            )}

            {combinedMessages.map(m => (
              <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "assistant" && (
                  <div className="w-8 h-8 rounded-full bg-ai flex items-center justify-center shrink-0">
                    <Bot className="h-4 w-4 text-background" />
                  </div>
                )}
                <div className={`max-w-[80%] rounded-lg p-3 text-sm whitespace-pre-wrap ${
                  m.role === "user" 
                    ? "bg-secondary text-foreground" 
                    : m.isError 
                      ? "bg-destructive/10 border border-destructive/20 text-destructive"
                      : "bg-card border border-border/50 text-foreground"
                }`}>
                  {m.content}
                  {m.isStreaming && m.content.length === 0 && (
                    <span className="text-muted-foreground animate-pulse">Thinking...</span>
                  )}
                  {m.isStreaming && m.content.length > 0 && (
                    <span className="inline-block w-2 h-4 ml-1 bg-muted-foreground/50 animate-pulse align-middle" />
                  )}
                </div>
                {m.role === "user" && (
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}
          </CardContent>
          <div className="p-4 border-t border-border/50 bg-card/50">
            <form onSubmit={e => { e.preventDefault(); handleSend(); }} className="flex gap-2">
              <Input 
                value={input} 
                onChange={e => setInput(e.target.value)} 
                placeholder="Ask about AAPL's 200-day SMA, or search 10-K documents..." 
                className="bg-background/50"
                disabled={activeStream?.isStreaming || isLoadingHistory}
              />
              <Button type="submit" disabled={activeStream?.isStreaming || isLoadingHistory || !input.trim()} className="bg-ai hover:bg-ai/90 text-background">
                <Send className="h-4 w-4" />
                <span className="sr-only">Send</span>
              </Button>
            </form>
          </div>
        </Card>
        
        <div className="w-80 hidden lg:flex flex-col gap-4">
          <Card className="flex-1 bg-background/50 border-border/50 p-4">
            <h3 className="font-medium text-sm text-foreground mb-4">Context & Tools</h3>
            <div className="space-y-3">
              {toolsRun.length === 0 && !activeStream?.isStreaming ? (
                <div className="text-xs text-muted-foreground">
                  Tool execution and retrieved context will appear here during processing.
                </div>
              ) : (
                toolsRun.map((t, i) => (
                  <div key={i} className="text-xs p-3 rounded-lg border border-border/50 bg-card">
                    <div className="flex items-center gap-2 mb-1">
                      <Wrench className="h-3 w-3 text-ai" />
                      <span className="font-mono text-foreground">{t.tool}()</span>
                    </div>
                    {t.summary ? (
                      <span className="text-muted-foreground line-clamp-3">{t.summary}</span>
                    ) : (
                      <span className="text-amber-500 animate-pulse">Running...</span>
                    )}
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
