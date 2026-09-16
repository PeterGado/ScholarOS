import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The backend never invalidates data out from under a valid session, and this is a
      // single-user local tool - a short, deliberate staleness window avoids refetch storms
      // without pretending the data updates in real time.
      staleTime: 10_000,
      retry: false,
    },
  },
});
