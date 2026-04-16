"use client";

import { useState, useRef, useEffect } from "react";
import { 
  MessageCircle, 
  X, 
  Send, 
  Loader2, 
  User, 
  Bot, 
  Sparkles,
  RefreshCw
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { chat, type ChatInput } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatWidgetProps {
  planId?: string;
}

export default function ChatWidget({ planId }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("confmind_chat_session");
      if (saved) return saved;
      const newId = Math.random().toString(36).substring(7);
      localStorage.setItem("confmind_chat_session", newId);
      return newId;
    }
    return Math.random().toString(36).substring(7);
  });
  
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Fetch initial message/history on mount
    const initChat = async () => {
      try {
        const response = await chat({
          session_id: sessionId,
          message: "", // Empty message to trigger welcome
          plan_id: planId
        });
        if (response.message) {
          setMessages([{ role: "assistant", content: response.message }]);
        }
      } catch (err) {
        console.error("Initial chat fetch failed:", err);
      }
    };
    initChat();
  }, [sessionId, planId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const chatInput: ChatInput = {
        session_id: sessionId,
        message: userMsg,
        plan_id: planId,
      };
      
      const response = await chat(chatInput);
      setMessages((prev) => [...prev, { role: "assistant", content: response.message }]);
    } catch (err) {
      console.error("Chat failed:", err);
      setMessages((prev) => [
        ...prev, 
        { role: "assistant", content: "Sorry, I'm having trouble connecting to the brain. Please try again later." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Chat Window */}
      {isOpen && (
        <Card className="mb-4 w-[380px] h-[520px] shadow-2xl border-primary/20 bg-background/90 backdrop-blur-xl flex flex-col animate-in slide-in-from-bottom-5 duration-300">
          <CardHeader className="p-4 border-b bg-primary/5 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-primary-foreground" />
              </div>
              <div>
                <CardTitle className="text-sm font-bold">ConfMind Agent</CardTitle>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Always-on AI</span>
                </div>
              </div>
            </div>
            <Button 
                variant="ghost" 
                size="icon" 
                className="rounded-full hover:bg-destructive/10 hover:text-destructive transition-colors"
                onClick={() => setIsOpen(false)}
            >
              <X className="w-4 h-4" />
            </Button>
          </CardHeader>
          
          <CardContent 
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-primary/10"
          >
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-3 opacity-60 px-4">
                <div className="p-4 rounded-2xl bg-muted/50 border border-border">
                  <Bot className="w-12 h-12 text-primary/40 mx-auto mb-2" />
                  <p className="text-sm font-medium">Hello! I'm your conference planning strategist.</p>
                  <p className="text-xs">Ask me about venues, speakers, or ways to optimize your revenue.</p>
                </div>
              </div>
            )}
            
            {messages.map((msg, i) => (
              <div 
                key={i} 
                className={cn(
                  "flex items-start gap-2.5 max-w-[85%] animate-in fade-in duration-300",
                  msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                )}
              >
                <div className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center shrink-0 border",
                  msg.role === "user" ? "bg-secondary/10 border-secondary/20" : "bg-primary/10 border-primary/20"
                )}>
                  {msg.role === "user" ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4 text-primary" />}
                </div>
                <div className={cn(
                  "px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed shadow-sm",
                  msg.role === "user" 
                    ? "bg-primary text-primary-foreground rounded-tr-none" 
                    : "bg-muted/80 backdrop-blur-sm border border-border/50 rounded-tl-none"
                )}>
                  {msg.content}
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex items-center gap-2 mr-auto max-w-[85%] animate-pulse">
                <div className="w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                </div>
                <div className="bg-muted px-4 py-2 rounded-2xl text-xs text-muted-foreground border border-border italic">
                  Asking the agents...
                </div>
              </div>
            )}
          </CardContent>

          <CardFooter className="p-4 pt-0">
            <form 
              onSubmit={(e) => { e.preventDefault(); handleSend(); }}
              className="flex w-full items-center gap-2 relative bg-muted/30 p-1.5 rounded-xl border border-border/50"
            >
              <input
                placeholder="Ask about your plan..."
                className="flex-1 bg-transparent border-none focus:ring-0 text-sm px-2 outline-none h-9"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                autoFocus
              />
              <Button 
                type="submit" 
                size="icon" 
                className="h-8 w-8 rounded-lg"
                disabled={!input.trim() || isLoading}
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </form>
          </CardFooter>
        </Card>
      )}

      {/* FAB */}
      <Button
        size="icon"
        className={cn(
          "h-14 w-14 rounded-full shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95 group",
          isOpen ? "bg-destructive hover:bg-destructive/90 rotate-90" : "bg-primary hover:bg-primary/90"
        )}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <X className="w-6 h-6" />
        ) : (
          <div className="relative">
             <MessageCircle className="w-6 h-6" />
             <span className="absolute -top-3 -right-3 flex h-5 w-5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-5 w-5 bg-secondary text-[10px] items-center justify-center font-bold text-secondary-foreground">1</span>
             </span>
          </div>
        )}
      </Button>
    </div>
  );
}
