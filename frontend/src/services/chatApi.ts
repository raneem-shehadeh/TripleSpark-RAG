import { z } from "zod";

export interface Source {
  source: string;
  page?: string | null | undefined;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export class ChatApiError extends Error {}

const apiBase = import.meta.env["VITE_API_BASE_URL"]?.trim().replace(/\/+$/, "") ?? "";
const API_URL = `${apiBase}/api/ask`;

const responseSchema = z.object({
  answer: z.string(),
  sources: z.array(z.object({ source: z.string().min(1), page: z.string().nullish() })),
});

export function isArabic(text: string): boolean {
  return /[\u0600-\u06FF]/.test(text);
}

export async function askQuestion(question: string, history: ChatTurn[] = []): Promise<AskResponse> {
  const q = question.trim();
  if (!q) throw new ChatApiError("Please type a question first.");
  const arabic = isArabic(q);
  const recent = history.slice(-8).map(({ role, content }) => ({
    role,
    content: content.slice(0, 1000),
  }));

  let response: Response;
  try {
    response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(recent.length ? { question: q, history: recent } : { question: q }),
    });
  } catch {
    throw new ChatApiError(
      arabic
        ? "تعذّر الاتصال بالخادم. تحقّق من الاتصال وحاول مرة أخرى."
        : "Could not reach the server. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    if (arabic && [429, 502, 503, 504].includes(response.status)) {
      const error = z.object({ detail: z.string().min(1) }).safeParse(
        await response.json().catch(() => null),
      );
      if (error.success) throw new ChatApiError(error.data.detail);
    }
    throw new ChatApiError(
      arabic
        ? `حدث خطأ في الخادم (${response.status}). حاول مرة أخرى.`
        : `The server returned an error (${response.status}). Please try again.`,
    );
  }

  const data: unknown = await response.json().catch(() => null);
  const parsed = responseSchema.safeParse(data);
  if (!parsed.success) {
    throw new ChatApiError(
      arabic ? "أرسل الخادم ردًا غير صالح." : "The server returned an invalid response.",
    );
  }
  return parsed.data;
}
