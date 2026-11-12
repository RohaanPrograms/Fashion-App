// How the app gets a session when it opens: reuse the one saved on this
// device, or start a guest. Every branch is checked with fake storage and a
// fake server, so no phone, browser or network is needed.
import type { AuthResponse, StoredSession, UserOut } from "../src/api/client";
import { needsRefresh, startSession, startupMessage, type StartupDeps } from "../src/auth/startup";

const NOW = 1_800_000_000_000;
const GUEST: UserOut = { id: "guest-1", email: null, is_anonymous: true };
const MEMBER: UserOut = { id: "user-1", email: "a@example.com", is_anonymous: false };

function authResponse(user: UserOut, access: string): AuthResponse {
  return {
    user,
    session: { access_token: access, refresh_token: `${access}-refresh`, token_type: "bearer", expires_in: 3600 },
  };
}

function saved(msUntilExpiry: number): StoredSession {
  return { access_token: "old-access", refresh_token: "old-refresh", expires_at: NOW + msUntilExpiry };
}

// Every dependency is a Jest mock ("jest.fn"), which records how it was called.
function fakeDeps(overrides: Partial<StartupDeps> = {}): StartupDeps {
  return {
    now: () => NOW,
    loadSaved: jest.fn(async (): Promise<StoredSession | null> => null),
    save: jest.fn(async (_s: StoredSession) => {}),
    clear: jest.fn(async () => {}),
    refresh: jest.fn(async (_t: string) => authResponse(MEMBER, "refreshed-access")),
    me: jest.fn(async (_t: string) => MEMBER),
    createGuest: jest.fn(async () => authResponse(GUEST, "guest-access")),
    wasSignedOut: jest.fn(async () => false),
    ...overrides,
  };
}

const fail = (status: number) => ({ status, detail: `failed with ${status}` });

test("a first visit creates a guest and saves its session", async () => {
  const deps = fakeDeps();

  const result = await startSession(deps);

  expect(result).toMatchObject({ kind: "ready", user: GUEST, isNewGuest: true });
  expect(deps.createGuest).toHaveBeenCalledTimes(1);
  expect(deps.save).toHaveBeenCalledWith(expect.objectContaining({ access_token: "guest-access" }));
});

test("a saved session is reused: no new guest, no refresh", async () => {
  const deps = fakeDeps({ loadSaved: jest.fn(async () => saved(30 * 60_000)) });

  const result = await startSession(deps);

  expect(result).toMatchObject({ kind: "ready", user: MEMBER, isNewGuest: false });
  expect(deps.me).toHaveBeenCalledWith("old-access");
  expect(deps.refresh).not.toHaveBeenCalled();
  expect(deps.createGuest).not.toHaveBeenCalled();
});

test("an expired session is refreshed, saved, then used", async () => {
  const deps = fakeDeps({ loadSaved: jest.fn(async () => saved(30_000)) }); // inside the 60 s margin

  const result = await startSession(deps);

  expect(deps.refresh).toHaveBeenCalledWith("old-refresh");
  expect(deps.save).toHaveBeenCalledWith(expect.objectContaining({ access_token: "refreshed-access" }));
  expect(deps.me).toHaveBeenCalledWith("refreshed-access");
  expect(result).toMatchObject({ kind: "ready", isNewGuest: false });
  expect(deps.createGuest).not.toHaveBeenCalled();
});

test("a session the server rejects is cleared and replaced by a new guest", async () => {
  const deps = fakeDeps({
    loadSaved: jest.fn(async () => saved(30_000)),
    refresh: jest.fn(async () => Promise.reject(fail(401))),
  });

  const result = await startSession(deps);

  expect(deps.clear).toHaveBeenCalled();
  expect(result).toMatchObject({ kind: "ready", user: GUEST, isNewGuest: true });
});

test("offline: the saved session is kept and no guest is created", async () => {
  const deps = fakeDeps({
    loadSaved: jest.fn(async () => saved(30 * 60_000)),
    me: jest.fn(async () => Promise.reject(fail(0))),
  });

  const result = await startSession(deps);

  expect(result).toEqual({ kind: "failed", error: fail(0) });
  expect(deps.clear).not.toHaveBeenCalled();
  expect(deps.createGuest).not.toHaveBeenCalled();
});

test("server trouble (503) is not mistaken for a dead session", async () => {
  const deps = fakeDeps({
    loadSaved: jest.fn(async () => saved(30 * 60_000)),
    me: jest.fn(async () => Promise.reject(fail(503))),
  });

  const result = await startSession(deps);

  expect(result).toMatchObject({ kind: "failed", error: { status: 503 } });
  expect(deps.clear).not.toHaveBeenCalled();
  expect(deps.createGuest).not.toHaveBeenCalled();
});

test("an unexpected error (not from the API) keeps the session too", async () => {
  const deps = fakeDeps({
    loadSaved: jest.fn(async () => saved(30 * 60_000)),
    me: jest.fn(async () => Promise.reject(new SyntaxError("Unexpected token <"))),
  });

  const result = await startSession(deps);

  expect(result.kind).toBe("failed");
  expect(deps.clear).not.toHaveBeenCalled();
});

test("the guest limit (429) is reported, not retried", async () => {
  const deps = fakeDeps({ createGuest: jest.fn(async () => Promise.reject(fail(429))) });

  const result = await startSession(deps);

  expect(result).toEqual({ kind: "failed", error: fail(429) });
  expect(deps.createGuest).toHaveBeenCalledTimes(1);
});

test("unreadable saved data is thrown away and a guest is created", async () => {
  const deps = fakeDeps({ loadSaved: jest.fn(async () => Promise.reject(new SyntaxError("bad JSON"))) });

  const result = await startSession(deps);

  expect(deps.clear).toHaveBeenCalled();
  expect(result).toMatchObject({ kind: "ready", isNewGuest: true });
});

test("a guest sign-in without a session is a failure, not a crash", async () => {
  const deps = fakeDeps({ createGuest: jest.fn(async () => ({ user: GUEST, session: null })) });

  const result = await startSession(deps);

  expect(result).toMatchObject({ kind: "failed", error: { status: 503 } });
  expect(deps.save).not.toHaveBeenCalled();
});

test("after a deliberate log-out, no guest is created: the visitor goes to login", async () => {
  const deps = fakeDeps({ wasSignedOut: jest.fn(async () => true) });

  const result = await startSession(deps);

  expect(result).toEqual({ kind: "signed-out" });
  expect(deps.createGuest).not.toHaveBeenCalled();
});

test("a saved session is used even if an old log-out note is still there", async () => {
  const deps = fakeDeps({
    loadSaved: jest.fn(async () => saved(30 * 60_000)),
    wasSignedOut: jest.fn(async () => true),
  });

  const result = await startSession(deps);

  expect(result).toMatchObject({ kind: "ready", user: MEMBER });
});

test("needsRefresh starts 60 s before expiry", () => {
  expect(needsRefresh(saved(61_000), NOW)).toBe(false);
  expect(needsRefresh(saved(60_000), NOW)).toBe(true);
  expect(needsRefresh(saved(-1), NOW)).toBe(true);
});

test.each([
  [0, "reach the server"],
  [429, "Too many new guests"],
  [503, "isn't ready"],
  [500, "isn't ready"],
])("startupMessage(%i) says %s", (status, words) => {
  expect(startupMessage({ status, detail: "x" })).toContain(words);
});
