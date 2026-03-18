const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"
const HOST_AGENT_URL = `${API_BASE_URL}/system`

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (response.status === 401) {
    window.location.reload()
    throw new Error("Session expired")
  }

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }

  return response.json()
}

async function fetchHostAgent(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${HOST_AGENT_URL}${endpoint}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (response.status === 401) {
    window.location.reload()
    throw new Error("Session expired")
  }

  if (!response.ok) {
    throw new Error(`Host Agent Error: ${response.statusText}`)
  }

  return response.json()
}

const API_BASE_URL_RAW = process.env.NEXT_PUBLIC_API_URL || "/api"

export async function uploadMedia(files: File[]) {
  const formData = new FormData()
  for (const file of files) {
    formData.append("files", file)
  }
  const response = await fetch(`${API_BASE_URL_RAW}/media/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
    // No Content-Type header — browser sets multipart boundary automatically
  })
  if (response.status === 401) {
    window.location.reload()
    throw new Error("Session expired")
  }
  if (!response.ok) {
    throw new Error(`Upload Error: ${response.statusText}`)
  }
  return response.json()
}

export const api = {
  accounts: {
    list: () => fetchApi("/accounts/"),
    create: (data: any) => fetchApi("/accounts/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi(`/accounts/${id}`, { method: "DELETE" }),
    createProfile: (id: number) => fetchApi(`/accounts/${id}/create-profile`, { method: "POST" }),
    fanpages: {
      list: (accountId: number) => fetchApi(`/accounts/${accountId}/fanpages`),
      create: (accountId: number, data: { fanpage_url: string; fanpage_name?: string }) =>
        fetchApi(`/accounts/${accountId}/fanpages`, { method: "POST", body: JSON.stringify(data) }),
      delete: (accountId: number, fanpageId: number) =>
        fetchApi(`/accounts/${accountId}/fanpages/${fanpageId}`, { method: "DELETE" }),
    },
  },
  campaigns: {
    list: () => fetchApi("/campaigns/"),
    create: (data: any) => fetchApi("/campaigns/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: any) => fetchApi(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    groups: (id: number) => fetchApi(`/campaigns/${id}/groups`),
    replaceGroups: (id: number, groups: any[]) =>
      fetchApi(`/campaigns/${id}/groups`, { method: "PUT", body: JSON.stringify({ groups }) }),
    schedulePreview: (id: number) => fetchApi(`/campaigns/${id}/schedule-preview`),
    generateSchedule: (id: number) =>
      fetchApi(`/campaigns/${id}/generate-schedule`, { method: "POST" }),
  },
  groups: {
    update: (id: number, data: any) =>
      fetchApi(`/groups/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
  logs: {
    list: () => fetchApi("/logs/"),
  },
  stats: () => fetchApi("/stats/"),
  system: {
    status: () => fetchApi("/system/status"),
  },
  hostAgent: {
    status: () => fetchHostAgent("/host/status"),
    startDonut: () => fetchHostAgent("/host/donut/start", { method: "POST" }),
    stopDonut: () => fetchHostAgent("/host/donut/stop", { method: "POST" }),
    donutProfiles: () => fetchApi("/system/donut/profiles"),
    donutRunProfile: (id: string) =>
      fetchApi(`/system/donut/profiles/${id}/run`, { method: "POST" }),
    donutKillProfile: (id: string) =>
      fetchApi(`/system/donut/profiles/${id}/kill`, { method: "POST" }),
  },
  fingerprintTests: {
    list: () => fetchApi("/fingerprint-tests/"),
    get: (id: number) => fetchApi(`/fingerprint-tests/${id}`),
    create: (data: { account_id?: number; visit_external_sites?: boolean }) =>
      fetchApi("/fingerprint-tests/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi(`/fingerprint-tests/${id}`, { method: "DELETE" }),
  },
  media: {
    upload: uploadMedia,
    delete: (filename: string) => fetchApi(`/media/${filename}`, { method: "DELETE" }),
    list: () => fetchApi("/media/list"),
  },
  workflows: {
    list: () => fetchApi("/workflows/"),
    get: (id: number) => fetchApi(`/workflows/${id}`),
    create: (data: any) =>
      fetchApi("/workflows/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      fetchApi(`/workflows/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi(`/workflows/${id}`, { method: "DELETE" }),
    run: (id: number, variables?: any) =>
      fetchApi(`/workflows/${id}/run`, { method: "POST", body: JSON.stringify(variables || {}) }),
    cancelRun: (id: number, runId: number) =>
      fetchApi(`/workflows/${id}/runs/${runId}/cancel`, { method: "POST" }),
    listRuns: (id: number) => fetchApi(`/workflows/${id}/runs`),
    getRun: (id: number, runId: number) => fetchApi(`/workflows/${id}/runs/${runId}`),
    getRunNodes: (id: number, runId: number) => fetchApi(`/workflows/${id}/runs/${runId}/nodes`),
    validate: (graphData: any) =>
      fetchApi("/workflows/validate", { method: "POST", body: JSON.stringify(graphData) }),
    nodeTypes: () => fetchApi("/workflows/node-types"),
  },
}
