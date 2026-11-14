// A swipe save that hits a dropped connection is tried once more; a real
// refusal is not; and it gives up after the second try.
import { RETRY_DELAY_MS, isTransient, withOneRetry } from "../src/api/retry";

const dropped = { status: 0, detail: "Could not reach the server" };
const outage = { status: 503, detail: "The service is temporarily unavailable." };
const refused = { status: 404, detail: "No such product" };
const noWait = jest.fn(() => Promise.resolve());

beforeEach(() => noWait.mockClear());

test("network drops and outages are transient; refusals are not", () => {
  expect([dropped, outage, { status: 502 }, { status: 504 }].map(isTransient)).toEqual([true, true, true, true]);
  expect([refused, { status: 401 }, { status: 500 }, new Error("x"), null].map(isTransient)).toEqual([
    false, false, false, false, false,
  ]);
});

test("a dropped connection is tried once more, after a pause, and then succeeds", async () => {
  const attempt = jest.fn().mockRejectedValueOnce(outage).mockResolvedValueOnce("saved");

  await expect(withOneRetry(attempt, noWait)).resolves.toBe("saved");
  expect(attempt).toHaveBeenCalledTimes(2);
  expect(noWait).toHaveBeenCalledWith(RETRY_DELAY_MS);
});

test("a refusal is not retried", async () => {
  const attempt = jest.fn().mockRejectedValue(refused);

  await expect(withOneRetry(attempt, noWait)).rejects.toBe(refused);
  expect(attempt).toHaveBeenCalledTimes(1);
  expect(noWait).not.toHaveBeenCalled();
});

test("it gives up after the second try and reports that failure", async () => {
  const attempt = jest.fn().mockRejectedValueOnce(dropped).mockRejectedValueOnce(outage);

  await expect(withOneRetry(attempt, noWait)).rejects.toBe(outage);
  expect(attempt).toHaveBeenCalledTimes(2);
});

test("success first time needs no retry", async () => {
  const attempt = jest.fn().mockResolvedValue("saved");

  await expect(withOneRetry(attempt, noWait)).resolves.toBe("saved");
  expect(attempt).toHaveBeenCalledTimes(1);
});
