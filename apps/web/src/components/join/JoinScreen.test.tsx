import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthUser } from "../../lib/auth";
import { setCopyLanguage } from "../../lib/copy/language";
import { callsTo, initOf, renderApp, stubApi } from "../../test-utils";

const auth = vi.hoisted(() => ({
  user: null as AuthUser | null,
  signInWithGoogle: vi.fn(),
  refreshIdToken: vi.fn(),
  order: [] as string[],
}));

vi.mock("../../lib/auth", () => ({
  getIdToken: vi.fn().mockResolvedValue("token-1"),
  signInWithGoogle: auth.signInWithGoogle,
  refreshIdToken: auth.refreshIdToken,
  subscribeAuthUser: (onUser: (user: AuthUser | null) => void) => {
    onUser(auth.user);
    return () => {};
  },
}));

const googleUser: AuthUser = { uid: "uid-7", isAnonymous: false, displayName: "Ari" };
const anonymousUser: AuthUser = { uid: "anon-1", isAnonymous: true, displayName: null };

function stubGps() {
  vi.stubGlobal("navigator", {
    geolocation: {
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: 0.51, longitude: 101.45 } } as GeolocationPosition),
    },
  });
}

function fillForm(code: string) {
  fireEvent.change(screen.getByLabelText("Kode undangan"), { target: { value: code } });
  fireEvent.change(screen.getByLabelText("Nama"), { target: { value: "Ari" } });
}

async function chooseGps() {
  fireEvent.click(screen.getByRole("button", { name: "Pakai lokasi saya" }));
  await screen.findByText("Lokasi rumah: 0.51000, 101.45000");
}

describe("join screen", () => {
  beforeEach(() => {
    setCopyLanguage("id");
    auth.refreshIdToken.mockImplementation(() => {
      auth.order.push("refresh");
      return Promise.resolve("token-2");
    });
    auth.order.length = 0;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("asks an anonymous visitor to sign in with Google", async () => {
    auth.user = anonymousUser;
    auth.signInWithGoogle.mockResolvedValue(googleUser);
    stubApi({});
    renderApp("/join");

    fireEvent.click(await screen.findByRole("button", { name: "Masuk dengan Google" }));

    await waitFor(() => expect(auth.signInWithGoogle).toHaveBeenCalledTimes(1));
    expect(screen.queryByLabelText("Kode undangan")).not.toBeInTheDocument();
  });

  it("shows the form to a Google user and names the missing fields on an empty send", async () => {
    auth.user = googleUser;
    const fetchMock = stubApi({});
    renderApp("/join");

    fireEvent.click(await screen.findByRole("button", { name: "Gabung" }));

    expect(await screen.findByText("Isi kode undangan.")).toBeInTheDocument();
    expect(screen.getByText("Pilih lokasi rumah.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST /api/join")).toHaveLength(0);
  });

  it("keeps the form and says so plainly when the code is wrong", async () => {
    auth.user = googleUser;
    stubGps();
    stubApi({
      "POST /api/join": () => Response.json({ detail: "invalid_invite_code" }, { status: 403 }),
    });
    renderApp("/join");
    await screen.findByLabelText("Kode undangan");
    fillForm("SALAH");
    await chooseGps();

    fireEvent.click(screen.getByRole("button", { name: "Gabung" }));

    expect(await screen.findByText(/Kode undangan salah/)).toBeInTheDocument();
    expect(screen.getByLabelText("Kode undangan")).toHaveValue("SALAH");
    expect(screen.getByLabelText("Nama")).toHaveValue("Ari");
    expect(auth.refreshIdToken).not.toHaveBeenCalled();
  });

  it("tells a staff account that it cannot join as a volunteer", async () => {
    auth.user = googleUser;
    stubGps();
    stubApi({
      "POST /api/join": () => Response.json({ detail: "already_has_role" }, { status: 409 }),
    });
    renderApp("/join");
    await screen.findByLabelText("Kode undangan");
    fillForm("BENAR");
    await chooseGps();

    fireEvent.click(screen.getByRole("button", { name: "Gabung" }));

    expect(await screen.findByText(/sudah punya peran/)).toBeInTheDocument();
    expect(auth.refreshIdToken).not.toHaveBeenCalled();
  });

  it("says when there are too many tries", async () => {
    auth.user = googleUser;
    stubGps();
    stubApi({
      "POST /api/join": () => Response.json({ detail: "too_many_attempts" }, { status: 429 }),
    });
    renderApp("/join");
    await screen.findByLabelText("Kode undangan");
    fillForm("X");
    await chooseGps();

    fireEvent.click(screen.getByRole("button", { name: "Gabung" }));

    expect(await screen.findByText(/Terlalu banyak percobaan/)).toBeInTheDocument();
  });

  it("posts the join, refreshes the token after it, then opens /v/{uid}", async () => {
    auth.user = googleUser;
    stubGps();
    const fetchMock = stubApi({
      "POST /api/join": () => {
        auth.order.push("post");
        return Response.json({ volunteer_id: "uid-7", created: true });
      },
    });
    const { router } = renderApp("/join");
    await screen.findByLabelText("Kode undangan");
    fillForm("RIAU-2026");
    fireEvent.change(screen.getByLabelText(/WhatsApp/), { target: { value: "+62 812-3456-7890" } });
    await chooseGps();
    fireEvent.change(screen.getByLabelText("Bahasa pesan"), { target: { value: "en" } });

    fireEvent.click(screen.getByRole("button", { name: "Join" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/v/uid-7"));
    expect(auth.order).toEqual(["post", "refresh"]);
    const call = callsTo(fetchMock, "POST /api/join")[0];
    expect(JSON.parse(String(initOf(call).body))).toEqual({
      invite_code: "RIAU-2026",
      name: "Ari",
      home: { lat: 0.51, lon: 101.45 },
      language: "en",
      whatsapp: "+6281234567890",
    });
  });
});
