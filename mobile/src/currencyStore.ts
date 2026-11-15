// The currency prices are shown in, shared by every screen. It starts from
// the device's region (en-CA -> CA$) and, once the visitor picks one on the
// Wardrobe tab, remembers that choice on the device. Like the start-over
// signal, it uses useSyncExternalStore: React's way for screens to follow a
// value that lives outside React, so changing it updates every screen at once.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";

import { chooseCurrency } from "./currency";
import { formatPrice } from "./format";

const SAVED_KEY = "display_currency";

function deviceLocale(): string | undefined {
  try {
    if (typeof navigator !== "undefined" && navigator.languages?.length) return navigator.languages[0];
    return Intl.DateTimeFormat().resolvedOptions().locale;
  } catch {
    return undefined;
  }
}

let current = chooseCurrency(null, deviceLocale());
const listeners = new Set<() => void>();
let loadStarted = false;

function emit() {
  listeners.forEach((listener) => listener());
}

// The saved choice lives in storage, which is read asynchronously: show the
// region's currency first, then switch if a different one was saved.
async function loadSaved() {
  if (loadStarted) return;
  loadStarted = true;
  try {
    const next = chooseCurrency(await AsyncStorage.getItem(SAVED_KEY), deviceLocale());
    if (next !== current) {
      current = next;
      emit();
    }
  } catch {
    // Storage unavailable: the region's currency is fine.
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  void loadSaved();
  return () => {
    listeners.delete(listener);
  };
}

export function useDisplayCurrency(): string {
  return useSyncExternalStore(subscribe, () => current);
}

export function setDisplayCurrency(code: string) {
  current = code;
  emit();
  AsyncStorage.setItem(SAVED_KEY, code).catch(() => {}); // remembering is a nicety
}

/** A price formatter for the chosen currency: price(p.price, p.currency). */
export function usePriceFormatter(): (price: number | null, currency: string) => string {
  const display = useDisplayCurrency();
  return (price, currency) => formatPrice(price, currency, display);
}
