"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Database, Server, Cpu, Globe, Monitor,
  Play, Square, RefreshCw, Loader2,
  CheckCircle2, XCircle, Terminal, AlertTriangle
} from "lucide-react"
import { api } from "@/lib/api"

interface ServiceStatus {
  status: "ok" | "error"
  detail: string
  workers?: string[]
}

interface DonutProfile {
  id: string
  name: string
  browser: string
  is_running: boolean
  [key: string]: any
}

// Label/icon mapping for known service keys from API response
const SERVICE_META: Record<string, { label: string; icon: any; controllable?: "donut" }> = {
  database: { label: "Baza danych", icon: Database },
  redis: { label: "Redis", icon: Server },
  api: { label: "FastAPI", icon: Monitor },
  celery_worker: { label: "Celery Worker", icon: Cpu },
  task_runner: { label: "Task Runner", icon: Cpu },
  donut_browser: { label: "Donut Browser", icon: Globe, controllable: "donut" },
}

function ServiceCard({
  label,
  icon: Icon,
  status,
  isLoading,
  controllable,
  onStart,
  onStop,
  actionLoading,
}: {
  label: string
  icon: any
  status: ServiceStatus | null
  isLoading: boolean
  controllable?: "donut" | "worker"
  onStart?: () => void
  onStop?: () => void
  actionLoading?: boolean
}) {
  const isOk = status?.status === "ok"

  return (
    <Card className="border-primary/10 bg-card/50">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{label}</CardTitle>
        <Icon className="h-4 w-4 text-primary" />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        ) : status ? (
          <div className="flex items-center gap-2">
            {isOk ? (
              <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">
                <CheckCircle2 className="mr-1 h-3 w-3" /> Aktywny
              </Badge>
            ) : (
              <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">
                <XCircle className="mr-1 h-3 w-3" /> Nieaktywny
              </Badge>
            )}
          </div>
        ) : (
          <Badge variant="secondary">Nieznany</Badge>
        )}
        <p className="text-xs text-muted-foreground mt-1">
          {isLoading ? "Sprawdzanie..." : status?.detail || "Brak danych"}
        </p>
        {status?.workers && status.workers.length > 0 && (
          <p className="text-xs text-muted-foreground mt-0.5 font-mono">
            {status.workers.join(", ")}
          </p>
        )}
        {controllable && onStart && onStop && (
          <div className="mt-3">
            {isOk ? (
              <Button
                size="xs"
                variant="outline"
                className="text-rose-500 border-rose-500/30 hover:bg-rose-500/10 hover:text-rose-500"
                disabled={actionLoading}
                onClick={onStop}
              >
                {actionLoading ? (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                ) : (
                  <Square className="mr-1 h-3 w-3" />
                )}
                Zatrzymaj
              </Button>
            ) : (
              <Button
                size="xs"
                variant="outline"
                className="text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-500"
                disabled={actionLoading}
                onClick={onStart}
              >
                {actionLoading ? (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                ) : (
                  <Play className="mr-1 h-3 w-3" />
                )}
                Uruchom
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function SystemPage() {
  const [systemStatus, setSystemStatus] = useState<Record<string, ServiceStatus> | null>(null)
  const [profiles, setProfiles] = useState<DonutProfile[]>([])
  const [statusLoading, setStatusLoading] = useState(true)
  const [profilesLoading, setProfilesLoading] = useState(true)
  const [profileActions, setProfileActions] = useState<Record<string, boolean>>({})
  const [profilePorts, setProfilePorts] = useState<Record<string, number>>({})
  const [serviceActions, setServiceActions] = useState<Record<string, boolean>>({})
  const [hostAgentAvailable, setHostAgentAvailable] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [donutError, setDonutError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      // Get backend status — keys are dynamic (standalone vs Docker mode)
      const backendData = await api.system.status()

      // Enrich donut_browser status via host agent endpoint
      try {
        const hostData = await api.hostAgent.status()
        setHostAgentAvailable(true)
        backendData.donut_browser = {
          status: hostData.donut_daemon?.api_available ? "ok" : "error",
          detail: hostData.donut_daemon?.api_available
            ? `API dostepne (daemon PID: ${hostData.donut_daemon.pid})`
            : hostData.donut_daemon?.running
              ? "Daemon uruchomiony, ale API niedostepne (otworz GUI Donut Browser)"
              : "Daemon nie uruchomiony",
        }
      } catch {
        setHostAgentAvailable(false)
      }

      setSystemStatus(backendData)
      setError(null)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setStatusLoading(false)
    }
  }, [])

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await api.hostAgent.donutProfiles()
      setProfiles(data.profiles || [])
      setDonutError(null)
    } catch (err: any) {
      setDonutError(err.message)
      setProfiles([])
    } finally {
      setProfilesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    fetchProfiles()
    const statusInterval = setInterval(fetchStatus, 10000)
    const profilesInterval = setInterval(fetchProfiles, 15000)
    return () => {
      clearInterval(statusInterval)
      clearInterval(profilesInterval)
    }
  }, [fetchStatus, fetchProfiles])

  const handleServiceAction = async (
    service: "donut",
    action: "start" | "stop"
  ) => {
    setServiceActions((prev) => ({ ...prev, [service]: true }))
    try {
      if (action === "start") await api.hostAgent.startDonut()
      else await api.hostAgent.stopDonut()
      await new Promise((r) => setTimeout(r, 2000))
      await fetchStatus()
      await fetchProfiles()
    } catch (err: any) {
      setError(`Blad ${action === "start" ? "uruchamiania" : "zatrzymywania"}: ${err.message}`)
    } finally {
      setServiceActions((prev) => ({ ...prev, [service]: false }))
    }
  }

  const handleRunProfile = async (id: string) => {
    setProfileActions((prev) => ({ ...prev, [id]: true }))
    try {
      const data = await api.hostAgent.donutRunProfile(id)
      if (data.remote_debugging_port) {
        setProfilePorts((prev) => ({ ...prev, [id]: data.remote_debugging_port }))
      }
      await fetchProfiles()
    } catch (err: any) {
      setError(`Blad uruchamiania profilu: ${err.message}`)
    } finally {
      setProfileActions((prev) => ({ ...prev, [id]: false }))
    }
  }

  const handleKillProfile = async (id: string) => {
    setProfileActions((prev) => ({ ...prev, [id]: true }))
    try {
      await api.hostAgent.donutKillProfile(id)
      setProfilePorts((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      await fetchProfiles()
    } catch (err: any) {
      setError(`Blad zatrzymywania profilu: ${err.message}`)
    } finally {
      setProfileActions((prev) => ({ ...prev, [id]: false }))
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">System</h2>
          <p className="text-muted-foreground">
            Status uslug i zarzadzanie profilami Donut Browser.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setStatusLoading(true)
            setProfilesLoading(true)
            fetchStatus()
            fetchProfiles()
          }}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Odswiez
        </Button>
      </div>

      {/* Global error */}
      {error && (
        <Card className="border-rose-500/20 bg-rose-500/5">
          <CardContent className="pt-4 pb-4">
            <p className="text-sm text-rose-500">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Service Status Grid — data-driven from API response */}
      <div>
        <h3 className="text-lg font-semibold mb-4 text-foreground">Status uslug</h3>
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
          {statusLoading ? (
            // Skeleton placeholders while loading
            Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="border-primary/10 bg-card/50">
                <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">...</CardTitle></CardHeader>
                <CardContent><Loader2 className="h-4 w-4 animate-spin text-primary" /></CardContent>
              </Card>
            ))
          ) : systemStatus ? (
            Object.entries(systemStatus).map(([key, svc]) => {
              const meta = SERVICE_META[key] || { label: key, icon: Server }
              return (
                <ServiceCard
                  key={key}
                  label={meta.label}
                  icon={meta.icon}
                  status={svc}
                  isLoading={false}
                  controllable={hostAgentAvailable ? meta.controllable : undefined}
                  onStart={
                    meta.controllable
                      ? () => handleServiceAction(meta.controllable!, "start")
                      : undefined
                  }
                  onStop={
                    meta.controllable
                      ? () => handleServiceAction(meta.controllable!, "stop")
                      : undefined
                  }
                  actionLoading={meta.controllable ? serviceActions[meta.controllable] : false}
                />
              )
            })
          ) : null}
        </div>
      </div>

      {/* Donut Browser Profiles */}
      <div>
        <h3 className="text-lg font-semibold mb-4 text-foreground">Profile Donut Browser</h3>

        {donutError ? (
          <Card className="border-amber-500/20 bg-amber-500/5">
            <CardContent className="pt-4 pb-4 flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
              <div className="flex-1">
                <p className="text-sm text-amber-500 font-medium">
                  Donut Browser API niedostepne
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Uruchom Donut Browser daemon aby zarzadzac profilami.
                </p>
              </div>
              {hostAgentAvailable && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-500 shrink-0"
                  disabled={serviceActions["donut"]}
                  onClick={() => handleServiceAction("donut", "start")}
                >
                  {serviceActions["donut"] ? (
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  ) : (
                    <Play className="mr-1 h-3 w-3" />
                  )}
                  Uruchom Daemon
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card className="border-primary/10 bg-card/50">
            <CardContent className="p-0">
              {profilesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-primary/10 hover:bg-transparent">
                      <TableHead>Nazwa</TableHead>
                      <TableHead>Silnik</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>CDP Port</TableHead>
                      <TableHead className="text-right">Akcje</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {profiles.map((profile) => (
                      <TableRow key={profile.id} className="border-primary/5">
                        <TableCell>
                          <div>
                            <span className="text-sm font-medium">{profile.name}</span>
                            <p className="text-xs text-muted-foreground font-mono mt-0.5">
                              {profile.id}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="capitalize">
                            {profile.browser || "wayfern"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {profile.is_running ? (
                            <Badge className="bg-emerald-500/15 text-emerald-500 border-none">
                              Uruchomiony
                            </Badge>
                          ) : (
                            <Badge className="bg-secondary text-muted-foreground border-none">
                              Zatrzymany
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {profilePorts[profile.id] ? (
                            <span className="font-mono text-xs text-primary">
                              :{profilePorts[profile.id]}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            {!profile.is_running ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-500"
                                disabled={profileActions[profile.id]}
                                onClick={() => handleRunProfile(profile.id)}
                              >
                                {profileActions[profile.id] ? (
                                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                ) : (
                                  <Play className="mr-1 h-3 w-3" />
                                )}
                                Uruchom
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-rose-500 border-rose-500/30 hover:bg-rose-500/10 hover:text-rose-500"
                                disabled={profileActions[profile.id]}
                                onClick={() => handleKillProfile(profile.id)}
                              >
                                {profileActions[profile.id] ? (
                                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                ) : (
                                  <Square className="mr-1 h-3 w-3" />
                                )}
                                Zatrzymaj
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {profiles.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                          Brak profili w Donut Browser
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Instructions */}
      <Card className="border-primary/10 bg-card/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">Informacje</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1.5">
              Donut Browser musi byc uruchomiony przed wykonywaniem zadan.
              Uzyj przycisku &quot;Uruchom&quot; na karcie Donut Browser lub uruchom go recznie.
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1.5">
              Profile przegladarki sa automatycznie tworzone przy dodawaniu kont.
              Mozesz nimi zarzadzac w tabeli ponizej.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
