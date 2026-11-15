// Prices in the visitor's currency: picked from their region, convertible
// with a fixed rate table, and always marked "≈" when converted (the
// catalogue's prices are made-up pounds; converting is for familiarity).
import {
  CURRENCIES,
  DEFAULT_CURRENCY,
  chooseCurrency,
  convert,
  currencyForLocale,
} from "../src/currency";
import { formatPrice } from "../src/format";

test("the region in the browser's language picks the currency", () => {
  expect(currencyForLocale("en-CA")).toBe("CAD");
  expect(currencyForLocale("fr-FR")).toBe("EUR");
  expect(currencyForLocale("de-DE")).toBe("EUR");
  expect(currencyForLocale("en-US")).toBe("USD");
  expect(currencyForLocale("en-GB")).toBe("GBP");
  expect(currencyForLocale("ur-PK")).toBe("PKR");
  expect(currencyForLocale("en_IN")).toBe("INR"); // underscore form, as some systems write it
  expect(currencyForLocale("ja-JP")).toBe("JPY");
});

test("an unknown or missing region keeps the catalogue's pounds", () => {
  expect(currencyForLocale("en")).toBe(DEFAULT_CURRENCY);
  expect(currencyForLocale("pt-BR")).toBe(DEFAULT_CURRENCY);
  expect(currencyForLocale(undefined)).toBe(DEFAULT_CURRENCY);
  expect(DEFAULT_CURRENCY).toBe("GBP");
});

test("a saved choice beats the region; an unknown saved code is ignored", () => {
  expect(chooseCurrency("JPY", "en-CA")).toBe("JPY");
  expect(chooseCurrency(null, "en-CA")).toBe("CAD");
  expect(chooseCurrency("XYZ", "en-CA")).toBe("CAD");
});

test("the ten offered currencies", () => {
  expect(CURRENCIES.map((c) => c.code)).toEqual(["GBP", "USD", "CAD", "EUR", "AUD", "NZD", "INR", "PKR", "AED", "JPY"]);
});

test("converting from pounds uses the rate table", () => {
  expect(convert(10, "GBP", "GBP")).toBe(10);
  expect(convert(10, "GBP", "CAD")).toBeCloseTo(18.851, 2);
  expect(convert(convert(10, "GBP", "EUR")!, "EUR", "GBP")).toBeCloseTo(10, 6);
  expect(convert(10, "GBP", "XYZ")).toBeNull();
});

test("a converted price is marked approximate", () => {
  expect(formatPrice(17.14, "GBP", "CAD")).toBe("≈ CA$32.31");
  expect(formatPrice(17.14, "GBP", "USD")).toBe("≈ $22.66");
});

test("the catalogue's own currency is shown exactly, with no ≈", () => {
  expect(formatPrice(17.14, "GBP", "GBP")).toBe("£17.14");
  expect(formatPrice(17.14, "GBP")).toBe("£17.14");
});

test("yen has no pence", () => {
  expect(formatPrice(17.14, "GBP", "JPY")).toBe("≈ ¥3,621");
});

test("a currency with no rate falls back to the original price", () => {
  expect(formatPrice(17.14, "GBP", "XYZ")).toBe("£17.14");
  expect(formatPrice(null, "GBP", "CAD")).toBe("Price unknown");
});
