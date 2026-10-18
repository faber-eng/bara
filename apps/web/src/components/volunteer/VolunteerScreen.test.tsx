import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { putFile, UploadTransferError } from "../../lib/volunteer/putFile";
import { callsTo, initOf, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));
vi.mock("../../lib/volunteer/putFile", async (original) => ({
  ...(await original<typeof import("../../lib/volunteer/putFile")>()),
  putFile: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("../../lib/volunteer/video", async (original) => {
  const actual = await original<typeof import("../../lib/volunteer/video")>();
  return { ...actual, checkedVideo: (file: Blob) => actual.checkedVideo(file, async () => 12) };
});
vi.mock("../../lib/volunteer/image", () => ({
  resizePhoto: vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" })),
}));

const task = {
  id: "task-1",
  case_id: "case-1",
  type: "dam_check",
  assignee_id: "uid-1",
  target: { lat: 0.4131, lon: 102.1548 },
  deadline_at: "2026-07-23T10:00:00Z",
  status: "open",
  cloud_task_name: null,
  attempt: 1,
  created_at: "2026-07-20T01:00:00Z",
  done_at: null,
};

const message = {
  id: "m1",
  thread: "volunteer",
  to_id: "uid-1",
  case_id: "case-1",
  lang: "id",
  text: "Halo Ari, sekat kanal perlu dicek.",
  text_en: "Hi Ari, a canal dam needs a check.",
  channel: "web",
  created_at: "2026-07-20T01:00:00Z",
  delivered: true,
};

const verdict = {
  subject: "canal_dam",
  dam_state: "broken",
  smoke: "none",
  hot_ground_signs: "none",
  open_flame: "no",
  transcript: null,
  transcript_en: null,
  reasons: ["gap in the wall"],
  confidence: 0.9,
  needs_human: false,
};

const judged = {
  id: "ev-1",
  task_id: "task-1",
  case_id: "case-1",
  kind: "photo",
  gcs_uri: "gs://b/ev-1",
  sha256: "0".repeat(64),
  point: null,
  captured_at: null,
  verdict,
  location_ok: true,
  uploaded_by: "uid-1",
  sample: false,
};

const inboxBody = { tasks: [task], messages: [message], evidence: [] };

function uploadHandlers(completeBody: unknown) {
  return {
    "GET /api/v/uid-1/inbox": () => Response.json(inboxBody),
    "POST /api/v/uid-1/uploads": () =>
      Response.json({
        evidence_id: "ev-1",
        upload_url: "https://gcs/put",
        headers: { "Content-Type": "image/jpeg" },
      }),
    "POST /api/v/uid-1/evidence/ev-1/complete": () => Response.json(completeBody),
  };
}

async function pickPhoto() {
  const input = await screen.findByLabelText("Berkas foto");
  const file = new File(["raw"], "dam.jpg", { type: "image/jpeg" });
  fireEvent.change(input, { target: { files: [file] } });
}

describe("volunteer screen", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_INBOX", "live");
    setCopyLanguage("id");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("shows the task card with the pin, the deadline and what to send", async () => {
    stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    expect(within(card).getByText("Sebelum Kamis, 23 Juli, 17.00 WIB")).toBeInTheDocument();
    expect(within(card).getByText("1 foto sekat, 1 pesan suara")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Buka di peta" })).toHaveAttribute(
      "href",
      expect.stringContaining("0.4131,102.1548"),
    );
    expect(screen.getByText("Halo Ari, sekat kanal perlu dicek.")).toBeInTheDocument();
  });

  it("says area, not dam, for a task whose case has no dam", async () => {
    const areaInbox = { ...inboxBody, area_case_ids: ["case-1"] };
    stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(areaInbox) });
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek area" });
    expect(within(card).getByText("1 foto area, 1 pesan suara")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "EN" }));

    const english = await screen.findByRole("article", { name: "Check the area" });
    expect(within(english).getByText("1 area photo, 1 voice note")).toBeInTheDocument();
  });

  it("switches the thread to English", async () => {
    stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
    renderApp("/v/uid-1");
    await screen.findByRole("article", { name: "Cek sekat kanal" });

    fireEvent.click(screen.getByRole("button", { name: "EN" }));

    expect(await screen.findByText("Hi Ari, a canal dam needs a check.")).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Check the canal dam" })).toBeInTheDocument();
  });

  it("shows an empty state when there is no open task", async () => {
    stubApi({
      "GET /api/v/uid-1/inbox": () => Response.json({ tasks: [], messages: [], evidence: [] }),
    });
    renderApp("/v/uid-1");

    expect(await screen.findByText("Belum ada tugas")).toBeInTheDocument();
  });

  it("says the page is not theirs on a 403", async () => {
    stubApi({ "GET /api/v/uid-9/inbox": () => new Response("no", { status: 403 }) });
    renderApp("/v/uid-9");

    expect(await screen.findByRole("alert")).toHaveTextContent("milik relawan lain");
  });

  it("offers a retry when the inbox fails", async () => {
    let calls = 0;
    stubApi({
      "GET /api/v/uid-1/inbox": () => {
        calls += 1;
        return calls === 1 ? new Response("x", { status: 500 }) : Response.json(inboxBody);
      },
    });
    renderApp("/v/uid-1");

    fireEvent.click(await screen.findByRole("button", { name: "Coba lagi" }));

    expect(await screen.findByRole("article", { name: "Cek sekat kanal" })).toBeInTheDocument();
  });

  it("uploads a photo through the signed URL and shows the verdict in plain words", async () => {
    const fetchMock = stubApi(uploadHandlers(judged));
    renderApp("/v/uid-1");

    await pickPhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Kirim foto" }));

    expect(await screen.findByText("Sekat terlihat jebol")).toBeInTheDocument();
    expect(screen.getByText("Jebol")).toBeInTheDocument();
    expect(screen.queryByText("Sampel")).not.toBeInTheDocument();
    expect(putFile).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "https://gcs/put",
        headers: { "Content-Type": "image/jpeg" },
      }),
    );
    const ticketCall = callsTo(fetchMock, "POST /api/v/uid-1/uploads")[0];
    expect(JSON.parse(String(initOf(ticketCall).body))).toMatchObject({
      task_id: "task-1",
      kind: "photo",
      sample: false,
    });
  });

  it("reads the verdict from the inbox when complete returns no evidence", async () => {
    let reads = 0;
    stubApi({
      ...uploadHandlers({ status: "ok" }),
      "GET /api/v/uid-1/inbox": () => {
        reads += 1;
        return Response.json({ ...inboxBody, evidence: reads > 1 ? [judged] : [] });
      },
    });
    renderApp("/v/uid-1");

    await pickPhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Kirim foto" }));

    expect(await screen.findByText("Sekat terlihat jebol")).toBeInTheDocument();
  });

  it("saves the upload on the phone when the signal is gone and sends it when it returns", async () => {
    vi.mocked(putFile).mockRejectedValueOnce(new UploadTransferError("offline"));
    const fetchMock = stubApi(uploadHandlers(judged));
    renderApp("/v/uid-1");

    await pickPhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Kirim foto" }));

    expect(await screen.findByText("Tersimpan di ponsel")).toBeInTheDocument();
    expect(await screen.findByText("1 kiriman menunggu sinyal")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST /api/v/uid-1/evidence/ev-1/complete")).toHaveLength(0);

    window.dispatchEvent(new Event("online"));

    await waitFor(() =>
      expect(callsTo(fetchMock, "POST /api/v/uid-1/evidence/ev-1/complete")).toHaveLength(1),
    );
    await waitFor(() =>
      expect(screen.queryByText("1 kiriman menunggu sinyal")).not.toBeInTheDocument(),
    );
  });

  it("keeps the photo and offers a retry when the server refuses the upload", async () => {
    vi.mocked(putFile).mockRejectedValueOnce(new UploadTransferError("too big", 413));
    stubApi(uploadHandlers(judged));
    renderApp("/v/uid-1");

    await pickPhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Kirim foto" }));
    fireEvent.click(await screen.findByRole("button", { name: "Kirim lagi" }));

    expect(await screen.findByText("Sekat terlihat jebol")).toBeInTheDocument();
    expect(putFile).toHaveBeenCalledTimes(2);
  });

  it("sends a typed reply to the agent", async () => {
    const fetchMock = stubApi({
      "GET /api/v/uid-1/inbox": () => Response.json(inboxBody),
      "POST /api/v/uid-1/chat": () => Response.json({}),
    });
    renderApp("/v/uid-1");

    fireEvent.change(await screen.findByLabelText("Tulis pesan ke Bara"), {
      target: { value: "Jalan banjir" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Kirim" }));

    await waitFor(() => expect(callsTo(fetchMock, "POST /api/v/uid-1/chat")).toHaveLength(1));
    expect(
      JSON.parse(String(initOf(callsTo(fetchMock, "POST /api/v/uid-1/chat")[0]).body)),
    ).toEqual({
      text: "Jalan banjir",
    });
    expect(await screen.findByText("Jalan banjir")).toBeInTheDocument();
  });

  it("says plainly when the reply is not sent", async () => {
    stubApi({
      "GET /api/v/uid-1/inbox": () => Response.json(inboxBody),
      "POST /api/v/uid-1/chat": () => new Response("x", { status: 404 }),
    });
    renderApp("/v/uid-1");

    fireEvent.change(await screen.findByLabelText("Tulis pesan ke Bara"), {
      target: { value: "Halo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Kirim" }));

    expect(await screen.findByText("Pesan belum terkirim. Coba lagi.")).toBeInTheDocument();
  });

  it("keeps a done task on screen without capture buttons", async () => {
    stubApi({
      "GET /api/v/uid-1/inbox": () =>
        Response.json({ ...inboxBody, tasks: [{ ...task, status: "done" }] }),
    });
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    expect(within(card).getByText("Selesai")).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Ambil foto" })).not.toBeInTheDocument();
  });

  it("hides a reassigned task", async () => {
    stubApi({
      "GET /api/v/uid-1/inbox": () =>
        Response.json({ ...inboxBody, tasks: [{ ...task, status: "reassigned" }] }),
    });
    renderApp("/v/uid-1");

    expect(await screen.findByText("Belum ada tugas")).toBeInTheDocument();
  });

  it("sends a sample photo with sample true and marks the evidence as a sample", async () => {
    const photoItem = {
      id: "broken-dam-1",
      kind: "photo",
      label: "Breached dam on the river Gour",
      credit: "Peter Bond, CC BY-SA 2.0",
      url: "/api/samples/broken-dam-1/file",
    };
    const fetchMock = stubApi({
      ...uploadHandlers({ ...judged, sample: true }),
      "GET /api/samples?kind=photo": () => Response.json([photoItem]),
      [`GET ${photoItem.url}`]: () => new Response("jpegbytes"),
    });
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    fireEvent.click(within(card).getByRole("button", { name: "Foto" }));
    fireEvent.click(await screen.findByRole("button", { name: "Pakai contoh" }));
    fireEvent.click(await screen.findByRole("button", { name: /Breached dam/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Kirim foto" }));

    expect(await screen.findByText("Sekat terlihat jebol")).toBeInTheDocument();
    expect(screen.getByText("Sampel")).toBeInTheDocument();
    const ticketCall = callsTo(fetchMock, "POST /api/v/uid-1/uploads")[0];
    expect(JSON.parse(String(initOf(ticketCall).body))).toMatchObject({ sample: true });
  });

  it("sends a sample voice note straight to the upload route", async () => {
    const voiceItem = {
      id: "damaged-dam-leak",
      kind: "voice",
      label: "Damaged dam, leaking",
      credit: "Faber Fathers",
      url: "/api/samples/damaged-dam-leak/file",
    };
    const fetchMock = stubApi({
      ...uploadHandlers({
        ...judged,
        kind: "audio",
        sample: true,
        verdict: {
          ...verdict,
          transcript: "Sekatnya jebol di sisi kiri",
          transcript_en: "The dam is broken on the left side",
        },
      }),
      "GET /api/samples?kind=voice": () => Response.json([voiceItem]),
      [`GET ${voiceItem.url}`]: () =>
        new Response(new Blob(["ogg"], { type: "audio/ogg" }), {
          headers: { "Content-Type": "audio/ogg" },
        }),
    });
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    fireEvent.click(within(card).getByRole("button", { name: "Suara" }));
    fireEvent.click(await screen.findByRole("button", { name: "Pakai contoh" }));
    fireEvent.click(await screen.findByRole("button", { name: /Damaged dam, leaking/ }));

    expect(await screen.findByText("Sekatnya jebol di sisi kiri")).toBeInTheDocument();
    expect(screen.getByText("Sampel")).toBeInTheDocument();
    const ticketCall = callsTo(fetchMock, "POST /api/v/uid-1/uploads")[0];
    expect(JSON.parse(String(initOf(ticketCall).body))).toMatchObject({
      kind: "audio",
      sample: true,
      content_type: "audio/ogg",
    });
  });

  it("sends a recorded video after checking its type and length", async () => {
    const fetchMock = stubApi(uploadHandlers({ ...judged, kind: "video" }));
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    const input = within(card).getByLabelText("Berkas video");
    const clip = new File(["mp4"], "clip.mp4", { type: "video/mp4" });
    fireEvent.change(input, { target: { files: [clip] } });

    expect(await screen.findByText("Sekat terlihat jebol")).toBeInTheDocument();
    const ticketCall = callsTo(fetchMock, "POST /api/v/uid-1/uploads")[0];
    expect(JSON.parse(String(initOf(ticketCall).body))).toMatchObject({
      kind: "video",
      content_type: "video/mp4",
      sample: false,
    });
  });

  it("refuses a video that is not MP4 or MOV before any upload", async () => {
    const fetchMock = stubApi(uploadHandlers(judged));
    renderApp("/v/uid-1");

    const card = await screen.findByRole("article", { name: "Cek sekat kanal" });
    const clip = new File(["webm"], "clip.webm", { type: "video/webm" });
    fireEvent.change(within(card).getByLabelText("Berkas video"), { target: { files: [clip] } });

    expect(await screen.findByRole("alert")).toHaveTextContent("MP4 atau MOV");
    expect(callsTo(fetchMock, "POST /api/v/uid-1/uploads")).toHaveLength(0);
  });

  describe("evidence row", () => {
    it("shows one button per kind the task needs", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      const row = await screen.findByRole("group", { name: "Tambah bukti" });
      const labels = within(row)
        .getAllByRole("button")
        .map((button) => button.textContent);
      expect(labels).toEqual(["Foto", "Suara", "Video"]);
    });

    it("omits the voice button for a repair task", async () => {
      stubApi({
        "GET /api/v/uid-1/inbox": () =>
          Response.json({ ...inboxBody, tasks: [{ ...task, type: "dam_repair" }] }),
      });
      renderApp("/v/uid-1");

      const row = await screen.findByRole("group", { name: "Tambah bukti" });
      expect(within(row).queryByRole("button", { name: "Suara" })).not.toBeInTheDocument();
      expect(within(row).getAllByRole("button")).toHaveLength(2);
    });

    it("opens a dialog with the real action and the sample choice", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      fireEvent.click(await screen.findByRole("button", { name: "Foto" }));

      const dialog = await screen.findByRole("dialog", { name: "Tambah foto" });
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(within(dialog).getByRole("button", { name: "Ambil foto" })).toBeInTheDocument();
      expect(within(dialog).getByRole("button", { name: "Pakai contoh" })).toBeInTheDocument();
      expect(within(dialog).getByRole("button", { name: "Batal" })).toBeInTheDocument();
    });

    it("opens the camera input from the real action and closes the dialog", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
      renderApp("/v/uid-1");

      fireEvent.click(await screen.findByRole("button", { name: "Foto" }));
      fireEvent.click(await screen.findByRole("button", { name: "Ambil foto" }));

      expect(click).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      click.mockRestore();
    });

    it("offers no sample choice for video", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      fireEvent.click(await screen.findByRole("button", { name: "Video" }));

      const dialog = await screen.findByRole("dialog", { name: "Tambah video" });
      expect(within(dialog).getByRole("button", { name: "Rekam video" })).toBeInTheDocument();
      expect(within(dialog).queryByRole("button", { name: "Pakai contoh" })).toBeNull();
    });

    it("marks a kind that was already sent as done", async () => {
      stubApi({
        "GET /api/v/uid-1/inbox": () =>
          Response.json({ ...inboxBody, evidence: [{ ...judged, kind: "photo" }] }),
      });
      renderApp("/v/uid-1");

      expect(await screen.findByRole("button", { name: "Foto, terkirim" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Suara" })).toBeInTheDocument();
    });

    it("closes on Escape and returns focus to the button", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      const trigger = await screen.findByRole("button", { name: "Foto" });
      trigger.focus();
      fireEvent.click(trigger);
      const dialog = await screen.findByRole("dialog");
      fireEvent.keyDown(dialog, { key: "Escape" });

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(trigger).toHaveFocus();
    });

    it("closes on Cancel", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      fireEvent.click(await screen.findByRole("button", { name: "Suara" }));
      fireEvent.click(await screen.findByRole("button", { name: "Batal" }));

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("keeps Tab inside the dialog", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      fireEvent.click(await screen.findByRole("button", { name: "Video" }));
      const dialog = await screen.findByRole("dialog");
      const cancel = within(dialog).getByRole("button", { name: "Batal" });
      cancel.focus();
      fireEvent.keyDown(dialog, { key: "Tab" });

      expect(within(dialog).getByRole("button", { name: "Rekam video" })).toHaveFocus();
    });
  });

  describe("chat thread", () => {
    function stubScrollBox(metrics: { scrollHeight: number; clientHeight: number }) {
      vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(metrics.scrollHeight);
      vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(metrics.clientHeight);
    }

    function replyMessage(id: string, text: string, at: string) {
      return { ...message, id, text, text_en: text, created_at: at };
    }

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("scrolls to the newest message on load", async () => {
      stubScrollBox({ scrollHeight: 900, clientHeight: 300 });
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      const log = await screen.findByRole("log", { name: "Percakapan dengan Bara" });
      await waitFor(() => expect(log.scrollTop).toBe(900));
    });

    it("shows the sender label and the time on each bubble", async () => {
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json(inboxBody) });
      renderApp("/v/uid-1");

      const log = await screen.findByRole("log", { name: "Percakapan dengan Bara" });
      expect(within(log).getByText("Bara")).toBeInTheDocument();
      expect(within(log).getByText("08.00")).toBeInTheDocument();
    });

    it("offers a jump button instead of scrolling when the reader is scrolled up", async () => {
      stubScrollBox({ scrollHeight: 900, clientHeight: 300 });
      let messages = [message];
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json({ ...inboxBody, messages }) });
      const { queryClient } = renderApp("/v/uid-1");

      const log = await screen.findByRole("log", { name: "Percakapan dengan Bara" });
      await waitFor(() => expect(log.scrollTop).toBe(900));
      log.scrollTop = 0;
      fireEvent.scroll(log);
      messages = [message, replyMessage("m2", "Siap, saya cek", "2026-07-20T01:05:00Z")];
      await queryClient.invalidateQueries({ queryKey: ["inbox", "uid-1"] });

      const jump = await screen.findByRole("button", { name: "Pesan baru" });
      expect(log.scrollTop).toBe(0);
      fireEvent.click(jump);
      expect(log.scrollTop).toBe(900);
      expect(screen.queryByRole("button", { name: "Pesan baru" })).not.toBeInTheDocument();
    });

    it("follows a new reply while the reader is at the bottom", async () => {
      stubScrollBox({ scrollHeight: 900, clientHeight: 300 });
      let messages = [message];
      stubApi({ "GET /api/v/uid-1/inbox": () => Response.json({ ...inboxBody, messages }) });
      const { queryClient } = renderApp("/v/uid-1");

      const log = await screen.findByRole("log", { name: "Percakapan dengan Bara" });
      await waitFor(() => expect(log.scrollTop).toBe(900));
      vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(1200);
      messages = [message, replyMessage("m2", "Siap, saya cek", "2026-07-20T01:05:00Z")];
      await queryClient.invalidateQueries({ queryKey: ["inbox", "uid-1"] });

      await waitFor(() => expect(log.scrollTop).toBe(1200));
      expect(screen.queryByRole("button", { name: "Pesan baru" })).not.toBeInTheDocument();
    });

    it("shows a sending state while the message goes out", async () => {
      let release: (response: Response) => void = () => {};
      stubApi({
        "GET /api/v/uid-1/inbox": () => Response.json(inboxBody),
        "POST /api/v/uid-1/chat": () =>
          new Promise<Response>((resolve) => {
            release = resolve;
          }),
      });
      renderApp("/v/uid-1");

      fireEvent.change(await screen.findByLabelText("Tulis pesan ke Bara"), {
        target: { value: "Halo" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Kirim" }));

      expect(await screen.findByRole("status")).toHaveTextContent("Mengirim");
      release(Response.json({}));
      await waitFor(() =>
        expect(screen.getByRole("status")).toHaveTextContent("Bara sedang menulis balasan"),
      );
    });
  });
});
