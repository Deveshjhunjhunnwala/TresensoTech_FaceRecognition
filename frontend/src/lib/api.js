export class ApiError extends Error {
  constructor(message, status = 500) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(payload.detail || "Request failed.", response.status);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function buildHeaders(token, headers = {}) {
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  };
}

export const apiClient = {
  getAuthStatus() {
    return request("/api/v2/auth/status");
  },
  login(username, password) {
    return request("/api/v2/auth/login", {
      method: "POST",
      headers: buildHeaders("", { "Content-Type": "application/json" }),
      body: JSON.stringify({ username, password }),
    });
  },
  setupCredentials(username, password, confirmPassword) {
    return request("/api/v2/auth/setup", {
      method: "POST",
      headers: buildHeaders("", { "Content-Type": "application/json" }),
      body: JSON.stringify({
        username,
        password,
        confirm_password: confirmPassword,
      }),
    });
  },
  resetCredentials(payload) {
    return request("/api/v2/auth/reset", {
      method: "POST",
      headers: buildHeaders("", { "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
  },
  me(token) {
    return request("/api/v2/auth/me", { headers: buildHeaders(token) });
  },
  get(path, token) {
    return request(path, { headers: buildHeaders(token) });
  },
  post(path, token, body = null, headers = {}) {
    return request(path, {
      method: "POST",
      headers: buildHeaders(token, headers),
      body,
    });
  },
  del(path, token) {
    return request(path, {
      method: "DELETE",
      headers: buildHeaders(token),
    });
  },
};
