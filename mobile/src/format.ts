// Formatting shared by every screen that shows a price.

export function formatPrice(price: number | null, currency: string): string {
  if (price === null) return "Price unknown";
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency }).format(price);
  } catch {
    // Intl throws on a currency code it doesn't know.
    return `${price.toFixed(2)} ${currency}`;
  }
}
