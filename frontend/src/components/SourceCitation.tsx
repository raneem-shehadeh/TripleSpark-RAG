import { FileText } from "lucide-react";
import type { Source } from "@/services/chatApi";

function httpUrl(source: string): string | undefined {
  const value = source.trim();
  if (!/^https?:\/\/[^\s]+$/i.test(value)) return;
  try {
    return new URL(value).hostname ? value : undefined;
  } catch {
    return undefined;
  }
}

export function SourceCitation({ source, page, arabic }: Source & { arabic: boolean }) {
  const href = httpUrl(source);
  const pageReference = page?.trim();
  const sourceClass = "min-w-0 font-medium [overflow-wrap:anywhere]";

  return (
    <span
      dir="ltr"
      className="flex min-w-0 max-w-full flex-wrap items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-xs text-accent-foreground"
    >
      <FileText className="h-3.5 w-3.5" />
      {href ? (
        <a href={href} dir="ltr" className={`${sourceClass} underline [unicode-bidi:isolate]`}>
          {href}
        </a>
      ) : (
        <bdi dir="auto" className={sourceClass}>
          {source}
        </bdi>
      )}
      {pageReference && pageReference.toLowerCase() !== "unknown" && (
        <>
          {" "}
          <bdi dir={arabic ? "rtl" : "ltr"} className="text-muted-foreground">
            {`${arabic ? "الصفحة" : "p."} ${pageReference}`}
          </bdi>
        </>
      )}
    </span>
  );
}
