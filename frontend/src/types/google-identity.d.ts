// Minimal ambient typing for the one Google Identity Services surface GoogleSignInButton.tsx
// actually uses (https://accounts.google.com/gsi/client, loaded dynamically at runtime) - not
// a full SDK typing, just enough to avoid `any` at the two call sites that need it.
export {};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: { client_id: string; callback: (response: { credential: string }) => void }): void;
          renderButton(
            parent: HTMLElement,
            options: { theme?: string; size?: string; width?: string | number; text?: string },
          ): void;
        };
      };
    };
  }
}
