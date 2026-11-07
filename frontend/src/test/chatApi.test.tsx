import { afterEach, describe, expect, it, vi } from "vitest";
import { askQuestion, isArabic } from "@/services/chatApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("chatApi", () => {
  it("rejects empty questions", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(askQuestion("   ")).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("detects Arabic text for RTL", () => {
    expect(isArabic("كيف أسجل؟")).toBe(true);
    expect(isArabic("How do I register?")).toBe(false);
  });

  it("posts a trimmed question and preserves returned string citations", async () => {
    const data = {
      answer: "الإجابة من الوثائق.",
      sources: [
        { source: "دليل الطالب", page: "76" },
        { source: "دليل التسجيل", page: "12-14" },
        { source: "دليل الكلية", page: "12, 15, 18" },
        { source: "https://example.edu/plan", page: "Unknown" },
        { source: "https://example.edu/plan/null", page: null },
        { source: "https://example.edu/plan/empty", page: "" },
        { source: "https://example.edu/plan/missing" },
      ],
    };
    const fetch = vi.fn().mockResolvedValue(Response.json(data));
    vi.stubGlobal("fetch", fetch);
    await expect(askQuestion("  كيف أسجل؟  ")).resolves.toEqual(data);
    expect(fetch).toHaveBeenCalledWith("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "كيف أسجل؟" }),
    });
  });

  it.each(["", "لا توجد معلومات كافية للإجابة عن هذا السؤال."])(
    "preserves a backend response with no citations (%s)",
    async (answer) => {
      const data = { answer, sources: [] };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(data)));
      await expect(askQuestion("Is this documented?")).resolves.toEqual(data);
    },
  );

  it("reports HTTP failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));
    await expect(askQuestion("How do I register?")).rejects.toThrow("500");
  });

  it("shows the backend's Arabic quota explanation", async () => {
    const detail = "بلغت خدمة الإجابة حد الاستخدام. حاول مرة أخرى لاحقًا.";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail }, { status: 429 })));
    await expect(askQuestion("كم العلامة المسموح إعادة المساق فيها؟")).rejects.toThrow(detail);
  });

  it("sends only the most recent eight bounded history messages", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ answer: "Example", sources: [] }));
    vi.stubGlobal("fetch", fetch);
    const history = Array.from({ length: 10 }, (_, index) => ({
      role: index % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `${index}${"a".repeat(1000)}`,
    }));
    await askQuestion("ما متطلبه السابق؟", history);
    expect(fetch).toHaveBeenCalledWith(
      "/api/ask",
      expect.objectContaining({
        body: JSON.stringify({
          question: "ما متطلبه السابق؟",
          history: history.slice(-8).map(({ role, content }) => ({
            role,
            content: content.slice(0, 1000),
          })),
        }),
      }),
    );
  });

  it("reports network failures in the question language", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(askQuestion("كيف أسجل؟")).rejects.toThrow("تعذّر الاتصال بالخادم");
  });

  it("rejects malformed responses instead of showing fabricated citations", async () => {
    const data = { answer: "Example", sources: [{ source: "guide.pdf", page: 3 }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(data)));
    await expect(askQuestion("How do I register?")).rejects.toThrow("invalid response");
  });
});
