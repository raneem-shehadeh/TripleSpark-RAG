import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { AlertTriangle, ArrowUp, SearchX, Zap, RotateCcw } from "lucide-react";
import { SourceCitation } from "@/components/SourceCitation";
import { askQuestion, isArabic, type ChatTurn, type Source } from "@/services/chatApi";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Triple Spark — AI Document Assistant" },
      { name: "description", content: "Ask questions in Arabic or English and get answers with cited sources." },
      { property: "og:title", content: "Triple Spark — AI Document Assistant" },
      { property: "og:description", content: "Ask questions in Arabic or English and get answers with cited sources." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ChatPage,
});

type Msg =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; text: string; sources: Source[]; question: string }
  | { id: number; role: "empty"; question: string }
  | { id: number; role: "error"; text: string; question: string };

const SUGGESTIONS = [
  "How do I register for courses?",
  "What are the tuition payment options?",
  "كيف أعترض على علامة الامتحان؟",
  "What are the prerequisites for Graduation Project 1 in Computer Engineering?",
];

let nextId = 1;

function Logo({ size = 40 }: { size?: number }) {
  return (
    <div
      className="bg-gradient-primary shadow-glow grid place-items-center rounded-xl text-primary-foreground"
      style={{ width: size, height: size }}
    >
      <div className="flex -space-x-1.5">
        <Zap className="h-3.5 w-3.5 fill-current" />
        <Zap className="h-3.5 w-3.5 -translate-y-1 fill-current" />
        <Zap className="h-3.5 w-3.5 fill-current" />
      </div>
    </div>
  );
}

function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(raw: string) {
    const question = raw.trim();
    if (!question || loading) return;
    setInput("");
    setMessages((m) => [...m, { id: nextId++, role: "user", text: question }]);
    setLoading(true);
    try {
      const history = messages
        .filter((message) => message.role === "assistant")
        .slice(-4)
        .flatMap<ChatTurn>((message) => [
          { role: "user", content: message.question },
          { role: "assistant", content: message.text },
        ]);
      const res = await askQuestion(question, history);
      setMessages((m) => [
        ...m,
        res.answer.trim()
          ? { id: nextId++, role: "assistant", text: res.answer, sources: res.sources, question }
          : { id: nextId++, role: "empty", question },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { id: nextId++, role: "error", text: e instanceof Error ? e.message : "Something went wrong.", question },
      ]);
    } finally {
      setLoading(false);
      taRef.current?.focus();
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }
  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const empty = messages.length === 0;
  const canSend = input.trim().length > 0 && !loading;

  return (
    <div className="flex h-dvh flex-col">
      <header className="glass sticky top-0 z-10 border-b">
        <div className="mx-auto flex max-w-4xl items-center gap-3 px-4 py-3">
          <Logo size={36} />
          <div className="flex-1">
            <h1 className="font-display text-lg font-bold leading-none">Triple Spark</h1>
            <p className="text-xs text-muted-foreground">AI document assistant</p>
          </div>
          {!empty && (
            <button
              onClick={() => setMessages([])}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs text-muted-foreground transition hover:bg-secondary hover:text-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" /> New chat
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {empty ? (
            <section className="flex min-h-[60vh] flex-col items-center justify-center text-center">
              <Logo size={72} />
              <h2 className="font-display mt-6 text-4xl font-bold sm:text-5xl">
                Welcome to <span className="text-gradient">Triple Spark</span>
              </h2>
              <p className="mt-3 max-w-md text-muted-foreground">
                Ask anything about your documents — in English or العربية — and get answers backed by sources.
              </p>
              <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    dir="auto"
                    onClick={() => send(s)}
                    className="glass rounded-xl border p-4 text-start text-sm transition hover:border-primary hover:bg-accent"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="space-y-6">
              {messages.map((m) => (
                <MessageView key={m.id} msg={m} onRetry={send} disabled={loading} />
              ))}
              {loading && <Typing />}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="border-t bg-background/80 backdrop-blur">
        <form onSubmit={onSubmit} className="mx-auto max-w-4xl px-4 py-3">
          <div className="glass flex items-end gap-2 rounded-2xl border p-2 focus-within:border-primary">
            <textarea
              ref={taRef}
              dir="auto"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask a question… / اكتب سؤالك…"
              aria-label="Message"
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-muted-foreground"
            />
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send"
              className="bg-gradient-primary shadow-glow flex h-11 shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold text-primary-foreground transition disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
            >
              <span className="hidden sm:inline">Send</span>
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">
            Press Enter to send, Shift+Enter for a new line.
          </p>
        </form>
      </footer>
    </div>
  );
}

function MessageView({ msg, onRetry, disabled }: { msg: Msg; onRetry: (q: string) => void; disabled: boolean }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          dir={isArabic(msg.text) ? "rtl" : "ltr"}
          className="bg-gradient-primary max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-md px-4 py-3 text-sm text-primary-foreground sm:max-w-[70%]"
        >
          {msg.text}
        </div>
      </div>
    );
  }

  const ar = isArabic(msg.role === "assistant" ? msg.text : msg.question);

  return (
    <div className="flex gap-3">
      <Logo size={32} />
      <div className="min-w-0 max-w-[85%] flex-1 sm:max-w-[75%]">
        {msg.role === "assistant" && (
          <div dir={ar ? "rtl" : "ltr"} className="glass rounded-2xl rounded-ss-md border px-4 py-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.text}</p>
            {msg.sources.length > 0 && (
              <div className="mt-4 border-t pt-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {ar ? "المصادر" : "Sources"}
                </p>
                <div className="flex flex-wrap gap-2">
                  {msg.sources.map((s, i) => (
                    <SourceCitation
                      key={`${s.source}-${s.page}-${i}`}
                      source={s.source}
                      page={s.page}
                      arabic={ar}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {msg.role === "empty" && (
          <div dir={ar ? "rtl" : "ltr"} className="glass flex gap-3 rounded-2xl rounded-ss-md border px-4 py-3">
            <SearchX className="mt-0.5 h-5 w-5 shrink-0 text-primary-glow" />
            <div className="text-sm">
              <p className="font-semibold">{ar ? "لم أجد معلومات حول ذلك" : "I couldn't find that information"}</p>
              <p className="mt-1 text-muted-foreground">
                {ar
                  ? "جرّب إعادة صياغة سؤالك أو السؤال عن التسجيل أو الرسوم أو الامتحانات."
                  : "Try rephrasing, or ask about registration, fees, or exams."}
              </p>
            </div>
          </div>
        )}
        {msg.role === "error" && (
          <div dir={ar ? "rtl" : "ltr"} className="flex gap-3 rounded-2xl rounded-ss-md border border-destructive/50 bg-destructive/10 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="text-sm">
              <p className="font-semibold">{ar ? "حدث خطأ" : "Something went wrong"}</p>
              <p className="mt-1 text-muted-foreground">{msg.text}</p>
              <button
                disabled={disabled}
                onClick={() => onRetry(msg.question)}
                className="mt-2 text-xs font-semibold text-primary-glow hover:underline disabled:opacity-50"
              >
                {ar ? "حاول مرة أخرى" : "Try again"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Typing() {
  return (
    <div className="flex gap-3" aria-live="polite" aria-label="Assistant is typing">
      <Logo size={32} />
      <div className="glass flex items-center gap-1.5 rounded-2xl rounded-ss-md border px-4 py-4">
        {[0, 1, 2].map((i) => (
          <span key={i} className="animate-dot h-2 w-2 rounded-full bg-primary-glow" style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  );
}
