"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Loader2, AlertTriangle, RotateCcw, Send, Sparkles, MapPin } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getTrip, askTripAssistant,
  type TripDetail, type AssistantMessage, type AssistantReference,
} from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

const SUGGESTED_PROMPTS = [
  "Bugünü özetle",
  "Yarın ne yapacağım?",
  "Bu gezide kaç farklı yer var?",
  "En yoğun gün hangisi?",
  "Bu gezide yürüyerek gezmek mantıklı mı?",
];

// İstemci de sunucuyla AYNI üst sınırı uygular — bkz.
// trip_assistant_service.py MAX_HISTORY_TURNS. İstemci daha fazla tutsa
// bile sunucuya yalnızca son N tur gönderilir; burada da aynı sınırla
// tutarlı kalınır (gereksiz büyük bir payload asla oluşturulmaz).
const MAX_HISTORY_TURNS = 6;

interface ChatMessage extends AssistantMessage {
  references?: AssistantReference[];
}

export default function TripAssistantPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = Number(params.id);

  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function load() {
    if (!tripId || isNaN(tripId)) {
      setError("Geçersiz gezi ID'si.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    getTrip(tripId)
      .then((res) => { setTrip(res); setLoading(false); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Gezi yüklenemedi."); setLoading(false); });
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setTimeout(() => load(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  function placeNameFor(ref: AssistantReference): string {
    const stop = trip?.days.flat().find((s) => s.place_id === ref.place_id);
    return stop?.name ?? "Durak";
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return; // boş mesaj / çift-gönderim koruması

    setSendError("");
    setLastFailedMessage(null);
    const userMessage: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);

    try {
      // Sunucuya SUNULAN geçmiş, bu son kullanıcı mesajı hariç, KENDİ
      // üst sınırıyla sınırlı (bkz. modül doc yorumu).
      const history = messages.slice(-MAX_HISTORY_TURNS).map(({ role, content }) => ({ role, content }));
      const result = await askTripAssistant(tripId, { message: trimmed, history });
      setMessages((prev) => [...prev, { role: "assistant", content: result.answer, references: result.references }]);
    } catch (e) {
      setMessages((prev) => prev.slice(0, -1)); // başarısız kullanıcı mesajını geri al
      setLastFailedMessage(trimmed);
      setSendError(e instanceof Error ? e.message : "Asistana ulaşılamadı.");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function focusStop(ref: AssistantReference) {
    router.push(`/trips/${tripId}?focusDay=${ref.day_index}&focusPlace=${ref.place_id}`);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" aria-label="Yükleniyor" />
      </div>
    );
  }

  if (error || !trip) {
    return (
      <div className="min-h-screen bg-bg">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-4 text-center">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Yüklenemedi</h2>
          <p className="text-text-secondary text-sm max-w-sm">{error}</p>
          <Button onClick={load}><RotateCcw className="w-4 h-4" /> Tekrar Dene</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg pb-6 flex flex-col">
      <Navbar />
      <div className="pt-28 px-4 md:px-8 max-w-3xl mx-auto w-full flex flex-col flex-1">
        <button
          onClick={() => router.push(`/trips/${tripId}`)}
          className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all text-[11px] font-bold uppercase tracking-widest mb-4 shrink-0"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> {trip.title}
        </button>

        <motion.h1
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="font-display font-black text-2xl text-text mb-4 flex items-center gap-2 shrink-0"
        >
          <Sparkles className="w-5 h-5 text-accent-text" /> AI Gezi Asistanı
        </motion.h1>

        {/* Sohbet — role="log" ekran okuyucuya yeni mesajları AYRI ayrı
           anons eder (bkz. Req 9/10 "VoiceOver"/"ARIA semantics"). */}
        <div
          role="log"
          aria-live="polite"
          aria-label="Sohbet"
          className="flex-1 min-h-[40vh] overflow-y-auto space-y-3 mb-4 pr-1"
        >
          {messages.length === 0 && (
            <div className="text-center py-10">
              <p className="text-text-secondary text-sm mb-4">
                Bu gezi hakkında bana soru sorabilirsin — yalnızca gezinin gerçek
                verisine bakarak cevap veririm.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="text-xs font-semibold px-3 py-2 rounded-full bg-surface2 text-text-secondary hover:bg-border hover:text-text transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${m.role === "user" ? "" : "w-full"}`}>
                <Card
                  className={`p-3 text-sm whitespace-pre-wrap ${
                    m.role === "user" ? "bg-accent/10 border-accent/25" : ""
                  }`}
                >
                  {m.content}
                </Card>
                {m.role === "assistant" && m.references && m.references.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {m.references.map((ref, ri) => (
                      <button
                        key={ri}
                        onClick={() => focusStop(ref)}
                        className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-full bg-route/10 border border-route/25 text-route hover:bg-route/20 transition-colors"
                      >
                        <MapPin className="w-3 h-3" /> {placeNameFor(ref)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <Card className="p-3 flex items-center gap-2 text-sm text-text-secondary">
                <Loader2 className="w-4 h-4 animate-spin" /> Düşünüyor…
              </Card>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {sendError && (
          <div role="alert" className="flex items-center justify-between gap-3 mb-3 p-3 rounded-md bg-destructive/10 border border-destructive/25 text-sm text-destructive">
            <span className="min-w-0">{sendError}</span>
            {lastFailedMessage && (
              <Button
                size="sm" variant="outline"
                onClick={() => sendMessage(lastFailedMessage)}
                className="shrink-0"
              >
                Tekrar Dene
              </Button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-center gap-2 shrink-0 sticky bottom-4">
          <label htmlFor="assistant-input" className="sr-only">Asistana mesaj yaz</label>
          <Input
            id="assistant-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Bu gezi hakkında bir şey sor…"
            disabled={sending}
            autoComplete="off"
          />
          <Button type="submit" disabled={sending || !input.trim()} aria-label="Gönder">
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
