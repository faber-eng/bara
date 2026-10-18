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
        <ExplanationText explanation={explanation} />
      </p>,
    );
    expect(container.textContent).toContain("Dry for 12 days.");
    expect(container.textContent).not.toContain("explain-v2");
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
