type QueryValue = string | number | boolean | null | undefined;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";

function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const base = API_BASE_URL ? new URL(path, API_BASE_URL) : new URL(path, window.location.origin);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        base.searchParams.set(key, String(value));
      }
    });
  }

  return API_BASE_URL ? base.toString() : `${base.pathname}${base.search}`;
}

async function parseResponseDetail(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    return await response.text();
  } catch {
    return null;
  }
}

function extractErrorMessage(status: number, detail: unknown) {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (detail && typeof detail === "object" && "detail" in detail) {
    const nested = Reflect.get(detail, "detail");
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }

  return `HTTP ${status}`;
}

export async function fetchJson<TResponse>(
  path: string,
  options: Omit<RequestInit, "body"> & {
    body?: BodyInit | null;
    query?: Record<string, QueryValue>;
  } = {}
) {
  const { query, headers, ...init } = options;
  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers: {
      Accept: "application/json",
      ...headers
    }
  });

  if (!response.ok) {
    const detail = await parseResponseDetail(response);
    throw new ApiError(response.status, detail, extractErrorMessage(response.status, detail));
  }

  if (response.status === 204) {
    return null as TResponse;
  }

  return (await response.json()) as TResponse;
}

export async function fetchOptionalJson<TResponse>(
  path: string,
  fallback: TResponse,
  options: Omit<RequestInit, "body"> & {
    body?: BodyInit | null;
    query?: Record<string, QueryValue>;
  } = {}
) {
  try {
    return await fetchJson<TResponse>(path, options);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 501)) {
      return fallback;
    }

    throw error;
  }
}

export function getGatewayQuery(search: string) {
  const urlSearchParams = new URLSearchParams(search);
  const gatewayQuery: Record<string, string> = {};

  ["ip", "user", "pass"].forEach((key) => {
    const value = urlSearchParams.get(key);
    if (value) {
      gatewayQuery[key] = value;
    }
  });

  return gatewayQuery;
}
