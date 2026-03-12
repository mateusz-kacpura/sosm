"use client"

import { useEffect, useState, useCallback, Fragment } from "react"
import Link from "next/link"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Plus, Link as LinkIcon, Clock, Play, Pause, Square,
  CheckCircle2, ChevronDown, ChevronRight, Loader2,
  Calendar, RotateCcw, Pencil,
} from "lucide-react"
import { api } from "@/lib/api"
import { BackgroundPicker, ClockPicker, getBgColor } from "./spreadsheet"

interface GroupEntry {
  id: number
  url: string
  content: string
  background_style: string | null
  order: number
  planned_at: string | null
  status: "completed" | "queued" | "pending" | "failed"
}

function CampaignSpreadsheet({ campaignId, isActive, onRefresh }: {
  campaignId: number
  isActive: boolean
  onRefresh: () => void
}) {
  const [groups, setGroups] = useState<GroupEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  const fetchGroups = useCallback(async () => {
    try {
      const data = await api.campaigns.groups(campaignId)
      // Enrich with status from schedule-preview
      const preview = await api.campaigns.schedulePreview(campaignId)
      const statusMap: Record<number, string> = {}
      for (const s of preview.schedule || []) {
        statusMap[s.group_id] = s.status
      }
      setGroups(data.map((g: any) => ({
        ...g,
        status: statusMap[g.id] || "pending",
      })))
    } catch {
      setGroups([])
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    fetchGroups()
    if (isActive) {
      const iv = setInterval(fetchGroups, 15000)
      return () => clearInterval(iv)
    }
  }, [fetchGroups, isActive])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await api.campaigns.generateSchedule(campaignId)
      await fetchGroups()
    } catch { /* ignore */ }
    setGenerating(false)
  }

  const pad = (n: number) => n.toString().padStart(2, "0")

  const getDateParts = (planned_at: string | null) => {
    if (!planned_at) return { date: "", time: "" }
    const dt = new Date(planned_at)
    return {
      date: `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`,
      time: `${pad(dt.getHours())}:${pad(dt.getMinutes())}`,
    }
  }

  const handleDatePartChange = async (groupId: number, planned_at: string | null, part: "date" | "time", value: string) => {
    const { date, time } = getDateParts(planned_at)
    let newDate = part === "date" ? value : date
    let newTime = part === "time" ? value : time
    if (!newDate && !newTime) {
      setGroups(prev => prev.map(g => g.id === groupId ? { ...g, planned_at: null, status: "pending" } : g))
      try {
        await api.groups.update(groupId, { planned_at: null })
        onRefresh()
      } catch { /* ignore */ }
      return
    }
    if (!newDate) newDate = new Date().toISOString().slice(0, 10)
    if (!newTime) newTime = "12:00"
    const iso = new Date(`${newDate}T${newTime}`).toISOString()
    setGroups(prev => prev.map(g => g.id === groupId ? { ...g, planned_at: iso, status: "pending" } : g))
    try {
      await api.groups.update(groupId, { planned_at: iso })
      onRefresh()
    } catch { /* ignore */ }
  }

  const handleBgChange = async (groupId: number, value: string) => {
    setGroups(prev => prev.map(g => g.id === groupId ? { ...g, background_style: value || null } : g))
    try {
      await api.groups.update(groupId, { background_style: value || null })
    } catch { /* ignore */ }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
      </div>
    )
  }

  if (groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        Brak grup w tej kampanii
      </p>
    )
  }

  const hasUnscheduled = groups.some(g => !g.planned_at && g.status !== "completed")

  const statusIcon = (s: string) => {
    switch (s) {
      case "completed": return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
      case "queued": return <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />
      case "failed": case "failed_retry": return <RotateCcw className="h-3.5 w-3.5 text-rose-500" />
      default: return <Square className="h-3.5 w-3.5 text-muted-foreground" />
    }
  }

  const statusLabel = (s: string) => {
    switch (s) {
      case "completed": return "Gotowe"
      case "queued": return "W kolejce"
      case "failed": case "failed_retry": return "Blad"
      default: return "Oczekuje"
    }
  }

  const statusClass = (s: string) => {
    switch (s) {
      case "completed": return "bg-emerald-500/15 text-emerald-500"
      case "queued": return "bg-primary/15 text-primary"
      case "failed": case "failed_retry": return "bg-rose-500/15 text-rose-500"
      default: return "bg-secondary text-muted-foreground"
    }
  }

  return (
    <div className="py-3 space-y-3">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs text-muted-foreground">
          {groups.filter(g => g.status === "completed").length}/{groups.length} opublikowanych
        </span>
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs border-primary/20 text-primary"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating
            ? <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            : <Calendar className="mr-1 h-3 w-3" />
          }
          {hasUnscheduled ? "Generuj harmonogram" : "Przelicz daty"}
        </Button>
      </div>

      {/* Spreadsheet header */}
      <div className="grid grid-cols-[2rem_1fr_1.5fr_3rem_8.5rem_5.5rem_5.5rem] gap-2 px-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
        <span>#</span>
        <span>Grupa</span>
        <span>Tresc</span>
        <span>Tlo</span>
        <span>Data</span>
        <span>Godzina</span>
        <span>Status</span>
      </div>

      {/* Rows */}
      {groups.map((g, idx) => {
        const { date: plannedDate, time: plannedTime } = getDateParts(g.planned_at)
        const isEditable = g.status !== "queued"

        const bgColor = g.background_style ? getBgColor(g.background_style) : undefined

        return (
          <div
            key={g.id}
            className={`grid grid-cols-[2rem_1fr_1.5fr_3rem_8.5rem_5.5rem_5.5rem] gap-2 px-2 py-1.5 rounded-md items-center text-xs ${
              g.status === "completed" ? "opacity-60" : ""
            }`}
          >
            <span className="text-muted-foreground font-mono">{idx + 1}.</span>
            <span className="truncate font-mono text-[11px]">
              {g.url.replace("https://www.facebook.com/groups/", "").replace("https://facebook.com/groups/", "")}
            </span>
            <span className="truncate text-muted-foreground">
              {g.content.slice(0, 60)}{g.content.length > 60 ? "..." : ""}
            </span>
            {isEditable ? (
              <BackgroundPicker
                value={g.background_style || ""}
                onChange={(v) => handleBgChange(g.id, v)}
              />
            ) : (
              <div className="flex justify-center">
                {bgColor ? (
                  <div className="w-6 h-6 rounded-sm border border-primary/20" style={{ backgroundColor: bgColor }} />
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            )}
            {isEditable ? (
              <input
                type="date"
                className="h-7 w-full rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                value={plannedDate}
                onChange={(e) => handleDatePartChange(g.id, g.planned_at, "date", e.target.value)}
              />
            ) : (
              <span className="text-xs font-mono px-2">
                {plannedDate || "-"}
              </span>
            )}
            {isEditable ? (
              <ClockPicker
                value={plannedTime}
                onChange={(v) => handleDatePartChange(g.id, g.planned_at, "time", v)}
              />
            ) : (
              <span className="text-xs font-mono px-2">
                {plannedTime || "-"}
              </span>
            )}
            <div className="flex items-center gap-1.5">
              {statusIcon(g.status)}
              <Badge className={`border-none text-[10px] ${statusClass(g.status)}`}>
                {statusLabel(g.status)}
              </Badge>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  async function fetchData() {
    try {
      const campaignsData = await api.campaigns.list()
      setCampaigns(campaignsData)
    } catch (err: any) {
      setError(err.message)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleStatusChange = async (id: number, status: string) => {
    try {
      // Auto-start worker when activating a campaign
      if (status === "AKTYWNA") {
        try {
          const hostStatus = await api.hostAgent.status()
          if (!hostStatus.celery_worker?.running) {
            await api.hostAgent.startWorker()
          }
        } catch { /* host agent unavailable — user will see it in /system */ }
      }
      await api.campaigns.update(id, { status })
      await fetchData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case "AKTYWNA":
        return (
          <Badge className="bg-primary/20 text-primary border-primary/30">
            <Play className="mr-1 h-3 w-3 fill-primary" /> Aktywna
          </Badge>
        )
      case "WSTRZYMANA":
        return (
          <Badge variant="secondary" className="bg-secondary/50 text-muted-foreground">
            <Pause className="mr-1 h-3 w-3" /> Wstrzymana
          </Badge>
        )
      case "ZAKOŃCZONA":
        return (
          <Badge className="bg-emerald-500/15 text-emerald-500 border-none">
            <CheckCircle2 className="mr-1 h-3 w-3" /> Zakonczona
          </Badge>
        )
      case "BŁĄD":
        return (
          <Badge variant="destructive" className="bg-rose-500/15 text-rose-500 border-none">
            Blad
          </Badge>
        )
      default:
        return (
          <Badge variant="outline" className="border-primary/20 text-muted-foreground">
            <Square className="mr-1 h-3 w-3" /> Szkic
          </Badge>
        )
    }
  }

  if (error) return <div className="text-rose-500">Blad: {error}</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Kampanie Automatyzacji</h2>
          <p className="text-muted-foreground">Planuj i zarzadzaj publikacjami w grupach.</p>
        </div>

        <Link href="/campaigns/new">
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
            <Plus className="mr-2 h-4 w-4" /> Nowa Kampania
          </Button>
        </Link>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead className="w-8"></TableHead>
                <TableHead>Nazwa</TableHead>
                <TableHead>Konto</TableHead>
                <TableHead>Grupy</TableHead>
                <TableHead>Utworzono</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((camp) => {
                const isExpanded = expandedId === camp.id
                return (
                  <Fragment key={camp.id}>
                    <TableRow
                      className="border-primary/5 hover:bg-secondary/50 cursor-pointer"
                      onClick={() => setExpandedId(isExpanded ? null : camp.id)}
                    >
                      <TableCell className="w-8 px-2">
                        {isExpanded
                          ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        }
                      </TableCell>
                      <TableCell className="font-medium">
                        <div className="flex flex-col">
                           <span>{camp.name}</span>
                           <span className="text-[10px] text-muted-foreground uppercase tracking-widest">ID: {camp.id}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">{camp.account_id}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="border-primary/20 text-primary">
                          <LinkIcon className="mr-1 h-3 w-3" /> {camp.groups_count ?? 0} grup
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {camp.created_at
                          ? new Date(camp.created_at).toLocaleDateString("pl-PL", {
                              day: "2-digit", month: "2-digit", year: "numeric",
                            })
                          : "-"
                        }
                      </TableCell>
                      <TableCell>{statusBadge(camp.status)}</TableCell>
                      <TableCell className="text-right space-x-1" onClick={(e) => e.stopPropagation()}>
                        <Link href={`/campaigns/${camp.id}/edit`}>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-primary">
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </Link>
                        {camp.status === "SZKIC" && (
                          <Button variant="ghost" size="sm" className="text-primary" onClick={() => handleStatusChange(camp.id, "AKTYWNA")}>
                            Start
                          </Button>
                        )}
                        {camp.status === "AKTYWNA" && (
                          <Button variant="ghost" size="sm" className="text-amber-500" onClick={() => handleStatusChange(camp.id, "WSTRZYMANA")}>
                            Wstrzymaj
                          </Button>
                        )}
                        {camp.status === "WSTRZYMANA" && (
                          <Button variant="ghost" size="sm" className="text-primary" onClick={() => handleStatusChange(camp.id, "AKTYWNA")}>
                            Wznow
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <TableRow key={`${camp.id}-timeline`} className="border-primary/5 hover:bg-transparent">
                        <TableCell colSpan={7} className="p-0 px-4 pb-4">
                          <CampaignSpreadsheet
                            campaignId={camp.id}
                            isActive={camp.status === "AKTYWNA"}
                            onRefresh={fetchData}
                          />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })}
              {campaigns.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Brak kampanii
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
