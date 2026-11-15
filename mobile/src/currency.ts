// Showing prices in the visitor's currency.
//
// The catalogue's prices are made up, in pounds (the H&M dataset has none),
// so converting them is about familiarity, not accuracy: every converted
// price is marked "≈". The rates are a FIXED table in this file, not a live
// service, so there is nothing to break or pay for.
//
// RATES: 1 GBP = …, from https://open.er-api.com/v6/latest/GBP, published
// 2026-11-15. To refresh, fetch that address and copy the ten numbers in.

export const DEFAULT_CURRENCY = "GBP"; // the catalogue's own

export type CurrencyOption = { code: string; label: string };

// Offered in the picker, in this order (agreed 2026-11-15).
export const CURRENCIES: CurrencyOption[] = [
  { code: "GBP", label: "£ British pound" },
  { code: "USD", label: "$ US dollar" },
  { code: "CAD", label: "CA$ Canadian dollar" },
  { code: "EUR", label: "€ Euro" },
  { code: "AUD", label: "A$ Australian dollar" },
  { code: "NZD", label: "NZ$ New Zealand dollar" },
  { code: "INR", label: "₹ Indian rupee" },
  { code: "PKR", label: "Rs Pakistani rupee" },
  { code: "AED", label: "AED UAE dirham" },
  { code: "JPY", label: "¥ Japanese yen" },
];

// Units of each currency per 1 GBP.
const PER_GBP: Record<string, number> = {
  GBP: 1,
  USD: 1.322068,
  CAD: 1.885115,
  EUR: 1.197824,
  AUD: 1.948825,
  NZD: 2.390654,
  INR: 124.560539,
  PKR: 365.849311,
  AED: 4.855292,
  JPY: 211.246522,
};

// Region (the "CA" in "en-CA") -> currency, for the offered currencies.
const EUROZONE = ["AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT",
  "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK"];
const CURRENCY_BY_REGION: Record<string, string> = {
  GB: "GBP", IM: "GBP", JE: "GBP", GG: "GBP",
  US: "USD",
  CA: "CAD",
  AU: "AUD",
  NZ: "NZD",
  IN: "INR",
  PK: "PKR",
  AE: "AED",
  JP: "JPY",
  ...Object.fromEntries(EUROZONE.map((r) => [r, "EUR"])),
};

/** "en-CA" -> "CAD"; a language with no region, or a region we don't offer -> GBP. */
export function currencyForLocale(locale: string | undefined | null): string {
  const region = locale?.match(/[-_]([A-Za-z]{2})(?:[-_]|$)/)?.[1]?.toUpperCase();
  return (region && CURRENCY_BY_REGION[region]) || DEFAULT_CURRENCY;
}

/** The currency to show: a saved choice (if it's one we offer), else the region's. */
export function chooseCurrency(saved: string | null | undefined, locale: string | undefined | null): string {
  if (saved && saved in PER_GBP) return saved;
  return currencyForLocale(locale);
}

/** Convert an amount between two offered currencies; null if either has no rate. */
export function convert(amount: number, from: string, to: string): number | null {
  const a = PER_GBP[from];
  const b = PER_GBP[to];
  if (a === undefined || b === undefined) return null;
  return (amount / a) * b;
}
