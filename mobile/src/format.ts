// Formatting shared by every screen that shows a price.

import { convert } from "./currency";

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency }).format(amount);
  } catch {
    // Intl throws on a currency code it doesn't know.
    return `${amount.toFixed(2)} ${currency}`;
  }
}

/** `price` is in `currency` (the catalogue's: GBP). With `display` given and
 *  different, it's converted and marked "≈", e.g. "≈ CA$32.31"; if there's
 *  no rate for `display`, the original price is shown. */
export function formatPrice(price: number | null, currency: string, display: string = currency): string {
  if (price === null) return "Price unknown";
  if (display !== currency) {
    const converted = convert(price, currency, display);
    if (converted !== null) return `≈ ${money(converted, display)}`;
  }
  return money(price, currency);
}
