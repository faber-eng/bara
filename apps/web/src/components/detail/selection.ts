export type OpsDetailKind = "cell" | "dam" | "case" | "review";

export type OpsDetail = { kind: OpsDetailKind; id: string };

export type OpsDetailSearch = {
  cell?: string;
  dam?: string;
  case?: string;
  review?: string;
};

export function detailFromSearch(search: OpsDetailSearch): OpsDetail | null {
  if (search.review !== undefined) return { kind: "review", id: search.review };
  if (search.case !== undefined) return { kind: "case", id: search.case };
  if (search.dam !== undefined) return { kind: "dam", id: search.dam };
  if (search.cell !== undefined) return { kind: "cell", id: search.cell };
  return null;
}

export function searchForDetail(
  detail: OpsDetail | null,
): Record<OpsDetailKind, string | undefined> {
  return {
    cell: detail?.kind === "cell" ? detail.id : undefined,
    dam: detail?.kind === "dam" ? detail.id : undefined,
    case: detail?.kind === "case" ? detail.id : undefined,
    review: detail?.kind === "review" ? detail.id : undefined,
  };
}
