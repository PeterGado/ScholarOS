import { useEffect } from "react";

/** Sets the page's <meta name="description"> content (SEO - the production checklist's "meta
 * titles and descriptions" item, 2026-10-10). Only worth wiring into the handful of routes
 * robots.txt/sitemap.xml actually allow search engines to index (/, /login, /register,
 * /privacy, /terms, /forgot-password) - every other route is Disallow'd there already, so a
 * unique description on an authenticated app page would have no SEO audience. Restores
 * index.html's own default on unmount so navigating to an unlisted route (which never calls
 * this hook) doesn't keep a stale description from whichever indexable page was visited last.
 */
const DEFAULT_DESCRIPTION =
  "ScholarOS is an AI writing assistant that reads your research documents and writing style, then helps you write with real citations grounded in the evidence you actually uploaded.";

export function useMetaDescription(description: string): void {
  useEffect(() => {
    const tag = document.querySelector('meta[name="description"]');
    if (!tag) return;
    const previous = tag.getAttribute("content");
    tag.setAttribute("content", description);
    return () => {
      tag.setAttribute("content", previous ?? DEFAULT_DESCRIPTION);
    };
  }, [description]);
}
