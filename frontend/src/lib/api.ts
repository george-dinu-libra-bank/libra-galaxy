const API_URL = "/api/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(
      res.status,
      payload?.detail ?? `${res.status} ${res.statusText}`,
      res.headers.get("x-request-id") ?? undefined,
    );
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
