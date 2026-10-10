import { useEffect } from "react";

const SITE_NAME = "ScholarOS";

/** Sets the browser tab title for the page it's called from (SEO + screen-reader route-change
 * announcement convention - a SPA's static index.html <title> otherwise never changes across
 * client-side navigation, found during a 2026-10-09 frontend audit). No cleanup/restore on
 * unmount: every route in this app calls this hook, so the next page's own call always
 * overwrites it - there's no route left without one that would need the previous value back.
 */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} - ${SITE_NAME}` : SITE_NAME;
  }, [title]);
}
