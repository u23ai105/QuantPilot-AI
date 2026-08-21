export class APIError extends Error {
  status: number;
  data?: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.data = data;
  }
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function fetchClient<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, headers, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  const token = sessionStorage.getItem("access_token");
  const config: RequestInit = {
    ...customConfig,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    if (response.status === 401) {
      // Trigger logout or clear session
      sessionStorage.removeItem("access_token");
      window.dispatchEvent(new Event("auth:unauthorized"));
    }

    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { detail: response.statusText };
    }
    
    let message = "An error occurred";
    if (errorData.detail) {
      if (Array.isArray(errorData.detail)) {
        // Pydantic validation error list
        message = errorData.detail.map((e: any) => `${e.loc?.slice(-1)?.[0] || 'field'}: ${e.msg}`).join(", ");
      } else if (typeof errorData.detail === "string") {
        message = errorData.detail;
      } else {
        message = JSON.stringify(errorData.detail);
      }
    }
    
    throw new APIError(response.status, message, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return await response.json();
}
