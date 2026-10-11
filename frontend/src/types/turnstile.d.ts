// Minimal ambient typing for the one Cloudflare Turnstile surface TurnstileWidget.tsx actually
// uses (https://challenges.cloudflare.com/turnstile/v0/api.js, loaded dynamically at runtime) -
// not a full SDK typing, same scope as google-identity.d.ts's own minimal typing.
export {};

declare global {
  interface Window {
    turnstile?: {
      render(
        container: HTMLElement,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
        },
      ): string;
      remove(widgetId: string): void;
    };
  }
}
