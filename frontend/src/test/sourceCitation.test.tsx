import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourceCitation } from "@/components/SourceCitation";

describe("SourceCitation", () => {
  it.each([{ page: "Unknown" }, { page: null }, { page: "" }, { page: " " }, {}])(
    "omits unavailable page information while preserving the URL (%j)",
    (pageProps) => {
      const source =
        "https://www.najah.edu/ar/academic/undergraduate-programs/program/computer-engineering/study-plan/";
      const { container } = render(<SourceCitation source={source} {...pageProps} arabic />);

      const link = screen.getByRole("link", { name: source });
      expect(link).toHaveAttribute("href", source);
      expect(link).toHaveAttribute("dir", "ltr");
      expect(container.textContent).toBe(source);
    },
  );

  it("keeps a known Arabic page label outside the clickable URL", () => {
    const source = "https://example.edu/plan";
    const { container } = render(<SourceCitation source={source} page="76" arabic />);
    const link = screen.getByRole("link", { name: source });
    const label = screen.getByText("الصفحة 76");
    expect(link).toHaveAttribute("href", source);
    expect(label).toHaveAttribute("dir", "rtl");
    expect(link).not.toContainElement(label);
    expect(container.textContent).toContain(`${source} الصفحة 76`);
  });

  it.each(["12-14", "12, 15, 18"])("keeps URL punctuation and page %s separate", (page) => {
    const source = "https://example.edu/خطة(قديمة)/?study_plan=2014-1#courses";
    render(<SourceCitation source={source} page={page} arabic={false} />);

    expect(screen.getByRole("link", { name: source })).toHaveAttribute("href", source);
    expect(screen.getByText(`p. ${page}`)).toBeVisible();
  });

  it.each(["دليل الطالب.pdf", "[Guide](https://example.edu/plan)", "javascript:alert(1)"])(
    "shows a non-URL source as literal text",
    (source) => {
      render(<SourceCitation source={source} page="Unknown" arabic={false} />);

      expect(screen.getByText(source)).toBeVisible();
      expect(screen.queryByText("Page unknown")).not.toBeInTheDocument();
      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    },
  );
});
