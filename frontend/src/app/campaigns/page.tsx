"use client"

import { useEffect, useState } from "react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog"
import { Plus, Link as LinkIcon, Clock, Play, Pause, Trash2, Square, CheckCircle2 } from "lucide-react"
import { api } from "@/lib/api"

interface GroupRow {
  url: string
  content: string
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [accounts, setAccounts] = useState<any[]>([])
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState("")
  const [accountId, setAccountId] = useState("")
  const [interval, setInterval] = useState("60")
  const [startAt, setStartAt] = useState("")
  const [groupRows, setGroupRows] = useState<GroupRow[]>([{ url: "", content: "" }])

  async function fetchData() {
    try {
      const [campaignsData, accountsData] = await Promise.all([
        api.campaigns.list(),
        api.accounts.list(),
      ])
      setCampaigns(campaignsData)
      setAccounts(accountsData)
    } catch (err: any) {
      setError(err.message)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const addGroupRow = () => {
    setGroupRows([...groupRows, { url: "", content: "" }])
  }

  const removeGroupRow = (index: number) => {
    setGroupRows(groupRows.filter((_, i) => i !== index))
  }

  const updateGroupRow = (index: number, field: keyof GroupRow, value: string) => {
    const updated = [...groupRows]
    updated[index][field] = value
    setGroupRows(updated)
  }

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const groups = groupRows
        .filter(g => g.url.trim() && g.content.trim())
        .map(g => ({ url: g.url.trim(), content: g.content.trim() }))

      await api.campaigns.create({
        name,
        account_id: parseInt(accountId),
        base_interval_minutes: parseInt(interval),
        groups,
        start_at: startAt ? new Date(startAt).toISOString() : null,
      })
      setName("")
      setAccountId("")
      setInterval("60")
      setStartAt("")
      setGroupRows([{ url: "", content: "" }])
      setIsDialogOpen(false)
      await fetchData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleStatusChange = async (id: number, status: string) => {
    try {
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
            <CheckCircle2 className="mr-1 h-3 w-3" /> Zakończona
          </Badge>
        )
      case "BŁĄD":
        return (
          <Badge variant="destructive" className="bg-rose-500/15 text-rose-500 border-none">
            Błąd
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

  if (error) return <div className="text-rose-500">Błąd: {error}</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Kampanie Automatyzacji</h2>
          <p className="text-muted-foreground">Planuj i zarządzaj publikacjami w grupach.</p>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger render={<Button className="bg-primary text-primary-foreground hover:bg-primary/90" />}>
              <Plus className="mr-2 h-4 w-4" /> Nowa Kampania
          </DialogTrigger>
          <DialogContent className="max-w-2xl bg-card border-primary/20 text-foreground max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-primary">Kreator Nowej Kampanii</DialogTitle>
              <DialogDescription>
                Zdefiniuj grupy docelowe z treścią per grupa.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateCampaign} className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Nazwa Kampanii</Label>
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
                  <Label htmlFor="account">Konto Wykonawcze</Label>
                  <select
                    id="account"
                    className="flex h-9 w-full rounded-md border border-primary/10 bg-secondary/50 px-3 py-1 text-sm"
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    required
                  >
                    <option value="">Wybierz konto...</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.fb_email}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="interval">Interwał (minuty)</Label>
                  <div className="flex items-center space-x-2">
                    <Clock className="h-4 w-4 text-primary" />
                    <Input
                      id="interval"
                      type="number"
                      className="bg-secondary/50 border-primary/10"
                      value={interval}
                      onChange={(e) => setInterval(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="startAt">Data i godzina startu</Label>
                  <Input
                    id="startAt"
                    type="datetime-local"
                    className="bg-secondary/50 border-primary/10"
                    value={startAt}
                    onChange={(e) => setStartAt(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Grupy docelowe</Label>
                  <Button type="button" variant="ghost" size="sm" onClick={addGroupRow} className="text-primary">
                    <Plus className="mr-1 h-3 w-3" /> Dodaj grupę
                  </Button>
                </div>
                {groupRows.map((row, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <div className="flex-1 space-y-1">
                      <Input
                        placeholder="URL grupy"
                        className="bg-secondary/50 border-primary/10"
                        value={row.url}
                        onChange={(e) => updateGroupRow(i, "url", e.target.value)}
                        required
                      />
                      <textarea
                        className="flex min-h-[60px] w-full rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                        placeholder="Treść posta dla tej grupy"
                        value={row.content}
                        onChange={(e) => updateGroupRow(i, "content", e.target.value)}
                        required
                      />
                    </div>
                    {groupRows.length > 1 && (
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeGroupRow(i)} className="text-rose-500 mt-1">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>

              <Button type="submit" className="w-full bg-primary text-primary-foreground font-bold">Utwórz Kampanię</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead>Nazwa</TableHead>
                <TableHead>Konto</TableHead>
                <TableHead>Grupy</TableHead>
                <TableHead>Start</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((camp) => (
                <TableRow key={camp.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                       <span>{camp.name}</span>
                       <span className="text-[10px] text-muted-foreground uppercase tracking-widest">ID: {camp.id}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">{camp.account_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-primary/20 text-primary">
                      <LinkIcon className="mr-1 h-3 w-3" /> {camp.groups?.length ?? 0} grup
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {camp.start_at ? new Date(camp.start_at).toLocaleString("pl-PL") : "Od razu"}
                  </TableCell>
                  <TableCell>{statusBadge(camp.status)}</TableCell>
                  <TableCell className="text-right space-x-1">
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
                        Wznów
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {campaigns.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
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
