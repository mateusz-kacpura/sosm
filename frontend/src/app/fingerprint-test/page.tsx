"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import {
  Fingerprint, Shield, Monitor, Palette, Box, Volume2,
  Type, Globe, Clock, Bot, Eye, Play, Trash2, Loader2, ChevronDown, ChevronUp
} from "lucide-react"
import { api } from "@/lib/api"

const categoryConfig: Record<string, { icon: any; label: string }> = {
  navigator: { icon: Globe, label: "Navigator" },
  canvas: { icon: Palette, label: "Canvas 2D" },
  webgl: { icon: Box, label: "WebGL" },
  screen: { icon: Monitor, label: "Ekran" },
  audio: { icon: Volume2, label: "AudioContext" },
  fonts: { icon: Type, label: "Czcionki" },
  webrtc: { icon: Shield, label: "WebRTC" },
  timezone: { icon: Clock, label: "Strefa Czasowa" },
  user_agent: { icon: Eye, label: "User-Agent" },
  automation_detection: { icon: Bot, label: "Detekcja Bota" },
}

function StatusBadge({ status }: { status: string }) {
  if (status === "pass") {
    return <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">Pass</Badge>
  }
  if (status === "warn") {
    return <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/20 border-none">Warn</Badge>
  }
  if (status === "fail") {
    return <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">Fail</Badge>
  }
  return <Badge variant="secondary">{status}</Badge>
}

function TestStatusBadge({ status }: { status: string }) {
  if (status === "COMPLETED") {
    return <Badge className="bg-emerald-500/15 text-emerald-500 border-none">Zakonczone</Badge>
  }
  if (status === "RUNNING" || status === "PENDING") {
    return <Badge className="bg-blue-500/15 text-blue-500 border-none">W trakcie</Badge>
  }
  if (status === "FAILED") {
    return <Badge className="bg-rose-500/15 text-rose-500 border-none">Blad</Badge>
  }
  return <Badge variant="secondary">{status}</Badge>
}

function ScoreDisplay({ score, status }: { score: number; status: string }) {
  const color = status === "pass" ? "text-emerald-500" : status === "warn" ? "text-amber-500" : "text-rose-500"
  const bgColor = status === "pass" ? "bg-emerald-500/10" : status === "warn" ? "bg-amber-500/10" : "bg-rose-500/10"
  const borderColor = status === "pass" ? "border-emerald-500/30" : status === "warn" ? "border-amber-500/30" : "border-rose-500/30"

  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border-2 ${borderColor} ${bgColor} p-8`}>
      <span className={`text-6xl font-bold ${color}`}>{score}</span>
      <span className="text-sm text-muted-foreground mt-2">/ 100</span>
      <StatusBadge status={status} />
    </div>
  )
}

function CategoryCard({ name, data }: { name: string; data: any }) {
  const config = categoryConfig[name]
  const Icon = config?.icon || Shield
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="border-primary/10 bg-card/50">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm font-medium">{config?.label || name}</CardTitle>
        </div>
        <StatusBadge status={data.status} />
      </CardHeader>
      <CardContent>
        {data.issues?.length > 0 && (
          <ul className="text-xs space-y-1 mb-2">
            {data.issues.map((issue: string, i: number) => (
              <li key={i} className="text-rose-400">- {issue}</li>
            ))}
          </ul>
        )}
        {data.issues?.length === 0 && (
          <p className="text-xs text-emerald-500">Brak problemow</p>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="mt-1 text-xs text-muted-foreground"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
          {expanded ? "Ukryj" : "Pokaz"} dane
        </Button>
        {expanded && (
          <pre className="mt-2 text-xs bg-secondary/50 rounded p-2 overflow-auto max-h-40">
            {JSON.stringify(data.data, null, 2)}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}

export default function FingerprintTestPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [tests, setTests] = useState<any[]>([])
  const [selectedTest, setSelectedTest] = useState<any>(null)
  const [selectedAccountId, setSelectedAccountId] = useState("")
  const [visitExternal, setVisitExternal] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pollingId, setPollingId] = useState<number | null>(null)

  const fetchTests = useCallback(async () => {
    try {
      const data = await api.fingerprintTests.list()
      setTests(data)
    } catch (err: any) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    async function fetchData() {
      try {
        const [accountsData, testsData] = await Promise.all([
          api.accounts.list(),
          api.fingerprintTests.list(),
        ])
        setAccounts(accountsData)
        setTests(testsData)
      } catch (err: any) {
        setError(err.message)
      }
    }
    fetchData()
  }, [])

  useEffect(() => {
    if (!pollingId) return
    const interval = setInterval(async () => {
      try {
        const result = await api.fingerprintTests.get(pollingId)
        if (result.status === "COMPLETED" || result.status === "FAILED") {
          setIsRunning(false)
          setPollingId(null)
          setSelectedTest(result)
          await fetchTests()
          clearInterval(interval)
        }
      } catch {
        setIsRunning(false)
        setPollingId(null)
        clearInterval(interval)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [pollingId, fetchTests])

  const handleRunTest = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const result = await api.fingerprintTests.create({
        account_id: selectedAccountId ? parseInt(selectedAccountId) : undefined,
        visit_external_sites: visitExternal,
      })
      setPollingId(result.id)
      await fetchTests()
    } catch (err: any) {
      setIsRunning(false)
      setError(err.message)
    }
  }

  const handleSelectTest = async (id: number) => {
    try {
      const result = await api.fingerprintTests.get(id)
      setSelectedTest(result)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.fingerprintTests.delete(id)
      if (selectedTest?.id === id) setSelectedTest(null)
      await fetchTests()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const analysis = selectedTest?.results?.analysis
  const selfTest = selectedTest?.results?.self_test
  const externalSites = selectedTest?.results?.external_sites

  if (error && !tests.length) return <div className="text-rose-500">Blad: {error}</div>

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Testy Fingerprint</h2>
          <p className="text-muted-foreground">Weryfikacja konfiguracji Camoufox przed uruchomieniem bota.</p>
        </div>
      </div>

      {/* Launch Controls */}
      <Card className="border-primary/10 bg-card/50">
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-muted-foreground">Konto (proxy)</label>
              <select
                className="h-9 rounded-md border border-primary/10 bg-secondary/50 px-3 text-sm"
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
              >
                <option value="">Bez proxy</option>
                {accounts.map((acc: any) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.fb_email} {acc.proxy_url ? `(${acc.proxy_url})` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="visitExternal"
                checked={visitExternal}
                onChange={(e) => setVisitExternal(e.target.checked)}
                className="rounded border-primary/20"
              />
              <label htmlFor="visitExternal" className="text-sm text-muted-foreground">
                Odwiedz zewnetrzne serwisy
              </label>
            </div>
            <Button
              onClick={handleRunTest}
              disabled={isRunning}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {isRunning ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Trwa test...</>
              ) : (
                <><Play className="mr-2 h-4 w-4" />Uruchom Test</>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {selectedTest && selectedTest.status === "COMPLETED" && analysis && (
        <Tabs defaultValue={0}>
          <TabsList>
            <TabsTrigger value={0}>Przeglad</TabsTrigger>
            <TabsTrigger value={1}>Kategorie</TabsTrigger>
            <TabsTrigger value={2}>Surowe Dane</TabsTrigger>
            {externalSites && Object.keys(externalSites).length > 0 && (
              <TabsTrigger value={3}>Zewnetrzne Serwisy</TabsTrigger>
            )}
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value={0}>
            <div className="grid gap-6 md:grid-cols-3 mt-4">
              <ScoreDisplay score={analysis.overall_score} status={analysis.overall_status} />
              <Card className="border-primary/10 bg-card/50 md:col-span-2">
                <CardHeader>
                  <CardTitle className="text-sm">Szczegoly testu</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">ID testu:</span>
                    <span className="font-mono">{selectedTest.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Proxy:</span>
                    <span>{selectedTest.proxy_url_used || "Brak"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Data:</span>
                    <span>{new Date(selectedTest.created_at).toLocaleString("pl-PL")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">User-Agent:</span>
                    <span className="text-xs max-w-[400px] truncate">{selfTest?.navigator?.userAgent || "-"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Platform:</span>
                    <span>{selfTest?.navigator?.platform || "-"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Ekran:</span>
                    <span>{selfTest?.screen?.width}x{selfTest?.screen?.height}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">WebGL Renderer:</span>
                    <span className="text-xs max-w-[400px] truncate">{selfTest?.webgl?.unmaskedRenderer || "-"}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Categories Tab */}
          <TabsContent value={1}>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mt-4">
              {Object.entries(analysis.categories || {}).map(([name, data]: [string, any]) => (
                <CategoryCard key={name} name={name} data={data} />
              ))}
            </div>
          </TabsContent>

          {/* Raw Data Tab */}
          <TabsContent value={2}>
            <Card className="border-primary/10 bg-card/50 mt-4">
              <CardContent className="pt-6">
                <pre className="text-xs bg-secondary/50 rounded p-4 overflow-auto max-h-[600px]">
                  {JSON.stringify(selfTest, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>

          {/* External Sites Tab */}
          {externalSites && Object.keys(externalSites).length > 0 && (
            <TabsContent value={3}>
              <div className="grid gap-4 md:grid-cols-3 mt-4">
                {Object.entries(externalSites).map(([key, site]: [string, any]) => (
                  <Card key={key} className="border-primary/10 bg-card/50">
                    <CardHeader>
                      <CardTitle className="text-sm capitalize">{key}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {site.visited ? (
                        <div className="space-y-2">
                          <Badge className="bg-emerald-500/15 text-emerald-500 border-none">Odwiedzone</Badge>
                          <p className="text-xs text-muted-foreground truncate">{site.url}</p>
                          {site.screenshot_path && (
                            <p className="text-xs text-primary">Screenshot zapisany</p>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <Badge className="bg-rose-500/15 text-rose-500 border-none">Blad</Badge>
                          <p className="text-xs text-rose-400">{site.error || "Nieznany blad"}</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          )}
        </Tabs>
      )}

      {selectedTest && selectedTest.status === "FAILED" && (
        <Card className="border-rose-500/20 bg-rose-500/5">
          <CardContent className="pt-6">
            <p className="text-rose-500">Test zakonczony bledem: {selectedTest.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* History Table */}
      <Card className="border-primary/10 bg-card/50">
        <CardHeader>
          <CardTitle className="text-sm">Historia testow</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead className="w-[60px]">ID</TableHead>
                <TableHead>Konto</TableHead>
                <TableHead>Proxy</TableHead>
                <TableHead>Wynik</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Data</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tests.map((t: any) => (
                <TableRow
                  key={t.id}
                  className={`border-primary/5 cursor-pointer ${selectedTest?.id === t.id ? "bg-primary/5" : "hover:bg-secondary/50"}`}
                  onClick={() => handleSelectTest(t.id)}
                >
                  <TableCell className="font-mono text-xs text-primary/70">{t.id}</TableCell>
                  <TableCell className="text-sm">{t.account_id || "-"}</TableCell>
                  <TableCell className="text-xs max-w-[150px] truncate">{t.proxy_url_used || "Brak"}</TableCell>
                  <TableCell>
                    {t.overall_score !== null && t.overall_score !== undefined ? (
                      <span className={`font-bold ${
                        t.overall_status === "pass" ? "text-emerald-500" :
                        t.overall_status === "warn" ? "text-amber-500" : "text-rose-500"
                      }`}>
                        {t.overall_score}/100
                      </span>
                    ) : "-"}
                  </TableCell>
                  <TableCell><TestStatusBadge status={t.status} /></TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {t.created_at ? new Date(t.created_at).toLocaleString("pl-PL") : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-rose-500 hover:text-rose-500 hover:bg-rose-500/10"
                      onClick={(e) => { e.stopPropagation(); handleDelete(t.id) }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {tests.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Brak testow
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
