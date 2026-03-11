const API_BASE_URL = "http://localhost:8010/api"

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

export const api = {
  accounts: {
    list: () => fetchApi("/accounts/"),
    create: (data: any) => fetchApi("/accounts/", { method: "POST", body: JSON.stringify(data) }),
  },
  campaigns: {
    list: () => fetchApi("/campaigns/"),
    create: (data: any) => fetchApi("/campaigns/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: any) => fetchApi(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
  logs: {
    list: () => fetchApi("/logs/"),
  }
}
