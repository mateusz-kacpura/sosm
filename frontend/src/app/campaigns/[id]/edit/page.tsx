"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter, useParams } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Plus, ArrowLeft, Calendar, Maximize2, Minimize2, ClipboardPaste, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import {
  GroupRow, SpreadsheetRow, SpreadsheetHeader, ScheduleGenerator,
  DEFAULT_COL_WIDTHS, MIN_COL_WIDTHS, SortDir,
} from "../../spreadsheet"

export default function EditCampaignPage() {
  const router = useRouter()
  const params = useParams()
  const campaignId = Number(params.id)

  const [loading, setLoading] = useState(true)
  const [accounts, setAccounts] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const [showGenerator, setShowGenerator] = useState(false)
  const [colWidths, setColWidths] = useState(DEFAULT_COL_WIDTHS)
  const [sortDir, setSortDir] = useState<SortDir>(null)

  const [name, setName] = useState("")
  const [accountId, setAccountId] = useState("")
  const [groupRows, setGroupRows] = useState<GroupRow[]>([])

  const pad = (n: number) => n.toString().padStart(2, "0")

  // Load campaign data
  useEffect(() => {
    async function load() {
      try {
        const [campaignsData, groupsData, accountsData] = await Promise.all([
          api.campaigns.list(),
          api.campaigns.groups(campaignId),
          api.accounts.list(),
        ])
        setAccounts(accountsData)

        const campaign = campaignsData.find((c: any) => c.id === campaignId)
        if (!campaign) {
          setError("Kampania nie znaleziona")
          setLoading(false)
          return
        }

        setName(campaign.name)
        setAccountId(String(campaign.account_id))

        // Convert groups to GroupRow format
        const rows: GroupRow[] = groupsData.map((g: any) => {
          let planned_date = ""
          let planned_time = ""
          if (g.planned_at) {
            const dt = new Date(g.planned_at)
            planned_date = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`
            planned_time = `${pad(dt.getHours())}:${pad(dt.getMinutes())}`
          }
          return {
            url: g.url,
            content: g.content,
            background_style: g.background_style || "",
            planned_date,
            planned_time,
          }
        })

        setGroupRows(rows.length > 0 ? rows : [{ url: "", content: "", background_style: "", planned_date: "", planned_time: "" }])
      } catch (err: any) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [campaignId])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && fullscreen) setFullscreen(false)
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [fullscreen])

  const startResize = useCallback((colIndex: number, e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = colWidths[colIndex]

    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX
      const newWidth = Math.max(MIN_COL_WIDTHS[colIndex], startWidth + delta)
      setColWidths(prev => {
        const next = [...prev]
        next[colIndex] = newWidth
        return next
      })
    }
    const onUp = () => {
      document.removeEventListener("mousemove", onMove)
      document.removeEventListener("mouseup", onUp)
    }
    document.addEventListener("mousemove", onMove)
    document.addEventListener("mouseup", onUp)
  }, [colWidths])

  const toggleSort = useCallback(() => {
    setSortDir(prev => {
      const next: SortDir = prev === null ? "asc" : prev === "asc" ? "desc" : null
      if (next === null) return null
      setGroupRows(rows => {
        const sorted = [...rows].sort((a, b) => {
          const dateA = `${a.planned_date} ${a.planned_time || "00:00"}`
          const dateB = `${b.planned_date} ${b.planned_time || "00:00"}`
          return next === "asc" ? dateA.localeCompare(dateB) : dateB.localeCompare(dateA)
        })
        return sorted
      })
      return next
    })
  }, [])

  const addGroupRow = () => {
    setGroupRows([...groupRows, { url: "", content: "", background_style: "", planned_date: "", planned_time: "" }])
  }

  const removeGroupRow = (index: number) => {
    setGroupRows(groupRows.filter((_, i) => i !== index))
  }

  const updateGroupRow = (index: number, field: keyof GroupRow, value: string) => {
    const updated = [...groupRows]
    updated[index][field] = value
    setGroupRows(updated)
  }

  const handleGenerate = (rows: GroupRow[]) => {
    const filled = groupRows.filter(r => r.url.trim() || r.content.trim())
    setGroupRows([...filled, ...rows])
    setShowGenerator(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      // Update campaign metadata
      await api.campaigns.update(campaignId, {
        name,
      })

      // Replace all groups
      const groups = groupRows
        .filter(g => g.url.trim())
        .map(g => {
          let planned_at: string | null = null
          if (g.planned_date) {
            const time = g.planned_time || "12:00"
            planned_at = new Date(`${g.planned_date}T${time}`).toISOString()
          }
          return {
            url: g.url.trim(),
            content: g.content.trim(),
            background_style: g.background_style || null,
            planned_at,
          }
        })

      await api.campaigns.replaceGroups(campaignId, groups)
      router.push("/campaigns")
    } catch (err: any) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  const content = (
    <div className={fullscreen ? "h-screen flex flex-col bg-background" : "space-y-6"}>
      {/* Header */}
      <div className={`flex items-center justify-between ${fullscreen ? "px-6 py-4 border-b border-primary/10 shrink-0" : ""}`}>
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 text-muted-foreground hover:text-primary"
            onClick={() => fullscreen ? setFullscreen(false) : router.push("/campaigns")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h2 className={`font-bold tracking-tight text-foreground ${fullscreen ? "text-xl" : "text-2xl"}`}>Edytuj Kampanie</h2>
            <p className="text-sm text-muted-foreground">Modyfikuj grupy, tresci i harmonogram publikacji.</p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-muted-foreground hover:text-primary"
          onClick={() => setFullscreen(!fullscreen)}
          title={fullscreen ? "Zamknij pelny ekran (Esc)" : "Pelny ekran"}
        >
          {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </Button>
      </div>

      {error && (
        <div className={`rounded-md bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-sm text-rose-500 ${fullscreen ? "mx-6 shrink-0" : ""}`}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className={fullscreen ? "flex flex-col flex-1 min-h-0" : "space-y-6"}>
        {/* Basic info */}
        <div className={fullscreen ? "px-6 py-3 border-b border-primary/10 shrink-0" : ""}>
          {fullscreen ? (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 flex-1">
                <Label htmlFor="name" className="text-xs shrink-0">Nazwa:</Label>
                <Input
                  id="name"
                  placeholder="np. Letnia Promocja"
                  className="bg-secondary/50 border-primary/10 h-8 text-sm max-w-xs"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="flex items-center gap-2 flex-1">
                <Label htmlFor="account" className="text-xs shrink-0">Konto:</Label>
                <select
                  id="account"
                  className="flex h-8 w-full max-w-xs rounded-md border border-primary/10 bg-secondary/50 px-3 py-1 text-sm"
                  value={accountId}
                  disabled
                >
                  <option value="">Wybierz konto...</option>
                  {accounts.map(acc => (
                    <option key={acc.id} value={acc.id}>{acc.fb_email}</option>
                  ))}
                </select>
              </div>
              <Button type="submit" size="sm" className="bg-primary text-primary-foreground font-bold px-6 h-8 shrink-0" disabled={submitting}>
                {submitting ? "Zapisywanie..." : "Zapisz zmiany"}
              </Button>
            </div>
          ) : (
            <Card className="border-primary/10 bg-card/50">
              <CardContent className="p-5">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Nazwa kampanii</Label>
                    <Input
                      id="name"
                      placeholder="np. Letnia Promocja"
                      className="bg-secondary/50 border-primary/10"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="account">Konto wykonawcze</Label>
                    <select
                      id="account"
                      className="flex h-9 w-full rounded-md border border-primary/10 bg-secondary/50 px-3 py-1 text-sm"
                      value={accountId}
                      disabled
                    >
                      <option value="">Wybierz konto...</option>
                      {accounts.map(acc => (
                        <option key={acc.id} value={acc.id}>{acc.fb_email}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Spreadsheet */}
        <div className={fullscreen ? "flex flex-col flex-1 min-h-0" : ""}>
          {fullscreen ? (
            <div className="flex flex-col flex-1 min-h-0">
              <div className="flex items-center justify-between px-6 py-2 border-b border-primary/10 shrink-0">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Calendar className="h-4 w-4 text-primary" />
                  Harmonogram publikacji
                  <span className="text-xs text-muted-foreground/60 ml-2">({groupRows.length} wierszy)</span>
                </div>
                <div className="flex items-center gap-1">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setShowGenerator(!showGenerator)} className="text-primary h-7 text-xs">
                    <ClipboardPaste className="mr-1 h-3 w-3" /> Wklej liste
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={addGroupRow} className="text-primary h-7 text-xs">
                    <Plus className="mr-1 h-3 w-3" /> Dodaj wiersz
                  </Button>
                </div>
              </div>

              {showGenerator && (
                <div className="px-6 py-3 border-b border-primary/10 shrink-0">
                  <ScheduleGenerator onGenerate={handleGenerate} />
                </div>
              )}

              <SpreadsheetHeader colWidths={colWidths} onResizeStart={startResize} sortDir={sortDir} onToggleSort={toggleSort} />

              <div className="flex-1 overflow-y-auto divide-y divide-primary/5">
                {groupRows.map((row, i) => (
                  <SpreadsheetRow key={i} row={row} index={i} total={groupRows.length} onUpdate={updateGroupRow} onRemove={removeGroupRow} colWidths={colWidths} />
                ))}
              </div>
            </div>
          ) : (
            <Card className="border-primary/10 bg-card/50">
              <CardContent className="p-0">
                <div className="flex items-center justify-between px-5 py-3 border-b border-primary/10">
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <Calendar className="h-4 w-4 text-primary" />
                    Harmonogram publikacji
                  </div>
                  <div className="flex items-center gap-1">
                    <Button type="button" variant="ghost" size="sm" onClick={() => setShowGenerator(!showGenerator)} className="text-primary h-7 text-xs">
                      <ClipboardPaste className="mr-1 h-3 w-3" /> Wklej liste
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={addGroupRow} className="text-primary h-7 text-xs">
                      <Plus className="mr-1 h-3 w-3" /> Dodaj wiersz
                    </Button>
                  </div>
                </div>

                {showGenerator && (
                  <div className="px-5 py-3 border-b border-primary/10">
                    <ScheduleGenerator onGenerate={handleGenerate} />
                  </div>
                )}

                <SpreadsheetHeader colWidths={colWidths} onResizeStart={startResize} sortDir={sortDir} onToggleSort={toggleSort} />

                <div className="divide-y divide-primary/5">
                  {groupRows.map((row, i) => (
                    <SpreadsheetRow key={i} row={row} index={i} total={groupRows.length} onUpdate={updateGroupRow} onRemove={removeGroupRow} colWidths={colWidths} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {!fullscreen && (
          <div className="flex items-center gap-3">
            <Button type="submit" className="bg-primary text-primary-foreground font-bold px-8" disabled={submitting}>
              {submitting ? "Zapisywanie..." : "Zapisz zmiany"}
            </Button>
            <Button type="button" variant="outline" className="border-primary/20" onClick={() => router.push("/campaigns")}>
              Anuluj
            </Button>
          </div>
        )}
      </form>
    </div>
  )

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-background">
        {content}
      </div>
    )
  }

  return content
}
