import { PropsWithChildren, useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { createAppQueryClient } from "@/app/query-client";

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(() => createAppQueryClient());

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
