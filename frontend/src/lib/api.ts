const API_BASE_URL = "http://localhost:8010/api"
const HOST_AGENT_URL = "http://localhost:8020"

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }

  return response.json()
}

async function fetchHostAgent(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${HOST_AGENT_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`Host Agent Error: ${response.statusText}`)
  }

  return response.json()
}

export const api = {
  accounts: {
    list: () => fetchApi("/accounts/"),
    create: (data: any) => fetchApi("/accounts/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi(`/accounts/${id}`, { method: "DELETE" }),
  },
  campaigns: {
    list: () => fetchApi("/campaigns/"),
    create: (data: any) => fetchApi("/campaigns/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: any) => fetchApi(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    groups: (id: number) => fetchApi(`/campaigns/${id}/groups`),
  },
  logs: {
    list: () => fetchApi("/logs/"),
  },
  stats: () => fetchApi("/stats/"),
  system: {
    status: () => fetchApi("/system/status"),
  },
  hostAgent: {
    status: () => fetchHostAgent("/status"),
    startDonut: () => fetchHostAgent("/donut/start", { method: "POST" }),
    stopDonut: () => fetchHostAgent("/donut/stop", { method: "POST" }),
    startWorker: () => fetchHostAgent("/worker/start", { method: "POST" }),
    stopWorker: () => fetchHostAgent("/worker/stop", { method: "POST" }),
    donutProfiles: () => fetchHostAgent("/donut/profiles"),
    donutRunProfile: (id: string) =>
      fetchHostAgent(`/donut/profiles/${id}/run`, { method: "POST" }),
    donutKillProfile: (id: string) =>
      fetchHostAgent(`/donut/profiles/${id}/kill`, { method: "POST" }),
  },
  fingerprintTests: {
    list: () => fetchApi("/fingerprint-tests/"),
    get: (id: number) => fetchApi(`/fingerprint-tests/${id}`),
    create: (data: { account_id?: number; visit_external_sites?: boolean }) =>
      fetchApi("/fingerprint-tests/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi(`/fingerprint-tests/${id}`, { method: "DELETE" }),
  },
}
