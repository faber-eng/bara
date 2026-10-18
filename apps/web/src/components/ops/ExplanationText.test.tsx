import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RankExplanation } from "../../lib/contracts";
import { detailCopy } from "../../lib/copy/detail";
import { ExplanationHow, ExplanationText } from "./ExplanationText";

const explanation: RankExplanation = {
  text: "Dry for 12 days.",
  cited: {},
  prompt_version: "explain-v2",
};

describe("rank explanation", () => {
  it("keeps the prompt version out of the visible text", () => {
    const { container } = render(
      <p>
        <ExplanationText explanation={explanation} copy={detailCopy("en")} />
      </p>,
    );
    expect(container.textContent).toContain("Dry for 12 days.");
    expect(container.textContent).not.toContain("explain-v2");
  });

  it("shows the summary then one labelled item per point", () => {
    const { container } = render(
      <div>
        <ExplanationText
          explanation={{
            ...explanation,
            text: "Summary 96.8. Rain low.",
            summary: "Summary 96.8.",
            cited: { drying_score: 96.8 },
            points: [
              { field: "rain_30d_mm", effect: "raises", text: "Rain low." },
              { field: "canal_dist_m", effect: "small", text: "Canal far." },
            ],
          }}
          copy={detailCopy("en")}
        />
      </div>,
    );
    const list = screen.getByRole("list", { name: "What drives the score" });
    expect(list.querySelectorAll("li")).toHaveLength(2);
    expect(list).toHaveTextContent("Pushes the score up");
    expect(list).toHaveTextContent("Adds little");
    expect(container.textContent).toContain("Summary 96.8.");
    expect(container.querySelector(".cited-number")).toHaveTextContent("96.8");
  });

  it("labels effects in Indonesian", () => {
    render(
      <ExplanationText
        explanation={{
          ...explanation,
          summary: "Ringkas.",
          points: [{ field: "a", effect: "lowers", text: "Basah." }],
        }}
        copy={detailCopy("id")}
      />,
    );
    expect(screen.getByText("Menahan skor")).toBeInTheDocument();
  });

  it("lists model and prompt version under the how-written line", () => {
    render(<ExplanationHow explanation={explanation} copy={detailCopy("en")} />);
    expect(screen.getByText("How this was written")).toBeInTheDocument();
    expect(screen.getByText("Gemini")).toBeInTheDocument();
    expect(screen.getByText("explain-v2")).toBeInTheDocument();
  });

  it("omits the version row when the explanation has none", () => {
    render(
      <ExplanationHow
        explanation={{ ...explanation, prompt_version: null }}
        copy={detailCopy("id")}
      />,
    );
    expect(screen.getByText("Cara teks ini ditulis")).toBeInTheDocument();
    expect(screen.queryByText("Versi prompt")).not.toBeInTheDocument();
  });
});
