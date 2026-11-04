/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  // Google Sign-In (2026-09-20): a public Client ID (from Google Cloud Console), not a secret -
  // safe to bake into the built bundle, same as any other VITE_* value.
  readonly VITE_GOOGLE_CLIENT_ID: string;
  readonly VITE_REQUIRE_INVITE_CODE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
