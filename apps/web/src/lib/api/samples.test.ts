import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { fetchSampleFile, fetchSamples, parseSamples, SampleFileError } from "./samples";

vi.mock("../auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const item = {
  id: "broken-dam-1",
  kind: "photo",
  label: "Breached dam on the river Gour",
  credit: "Peter Bond, CC BY-SA 2.0",
  url: "/api/samples/broken-dam-1/file",
};

describe("samples API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses the listing", () => {
    expect(parseSamples([item])[0]?.label).toBe("Breached dam on the river Gour");
  });

  it("rejects an unknown kind", () => {
    expect(() => parseSamples([{ ...item, kind: "video" }])).toThrow();
  });

  it("lists one kind", async () => {
    const fetchMock = stubApi({ "GET /api/samples?kind=photo": () => Response.json([item]) });

    const samples = await fetchSamples("photo");

    expect(samples).toHaveLength(1);
    expect(callsTo(fetchMock, "GET /api/samples?kind=photo")).toHaveLength(1);
  });

  it("downloads the file as a blob", async () => {
    stubApi({ [`GET ${item.url}`]: () => new Response("jpegbytes", { status: 200 }) });

    const blob = await fetchSampleFile(parseSamples([item])[0] ?? (item as never));

    expect(await blob.text()).toBe("jpegbytes");
  });

  it("throws a named error when the file is missing", async () => {
    stubApi({});

    await expect(
      fetchSampleFile(parseSamples([item])[0] ?? (item as never)),
    ).rejects.toBeInstanceOf(SampleFileError);
  });
});
