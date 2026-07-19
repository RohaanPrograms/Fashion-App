// App-wide configuration values.

// The base URL of your FastAPI backend.
//
// IMPORTANT: "localhost" means "this device". That is fine on the web preview
// or an iOS simulator, but when you run the app on a real phone through Expo Go,
// "localhost" points at the PHONE, not your computer. In that case set your
// computer's local network IP address instead, e.g. http://192.168.1.42:8000
// (find it with `ipconfig` on Windows).
//
// You can override this without editing code by creating a `.env` file in the
// mobile/ folder with a line like:
//   EXPO_PUBLIC_API_URL=http://192.168.1.42:8000
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
