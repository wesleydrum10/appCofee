import { getCsrfToken } from "./csrf.js";

export async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout ?? 10000);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Accept": "application/json",
        "X-CSRFToken": getCsrfToken(),
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || "Não foi possível concluir a ação.");
    }
    return data;
  } finally {
    window.clearTimeout(timeout);
  }
}
