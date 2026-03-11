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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Image as ImageIcon,
  Search
} from "lucide-react"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"

export default function LogsPage() {
  const [logs, setLogs] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  useEffect(() => {
    async function fetchLogs() {
      try {
        const data = await api.logs.list()
        setLogs(data)
      } catch (err: any) {
        setError(err.message)
      }
    }
    fetchLogs()
  }, [])

  const filteredLogs = logs.filter(log => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (log.campaign_name || "").toLowerCase().includes(q) ||
      (log.status || "").toLowerCase().includes(q) ||
      (log.error_message || "").toLowerCase().includes(q)
    )
  })

  if (error) return <div className="text-rose-500">Błąd: {error}</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Historia Operacji</h2>
          <p className="text-muted-foreground">Szczegółowy dziennik zdarzeń bota Playwright.</p>
        </div>
        <div className="flex w-full max-w-sm items-center space-x-2">
           <div className="relative flex-1">
             <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
             <Input
               placeholder="Szukaj po kampanii lub statusie..."
               className="pl-8 bg-secondary/50 border-primary/10"
               value={search}
               onChange={(e) => setSearch(e.target.value)}
             />
           </div>
        </div>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead className="w-[80px]">ID</TableHead>
                <TableHead>Kampania</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Błąd</TableHead>
                <TableHead>Próby</TableHead>
                <TableHead>Data i Czas</TableHead>
                <TableHead className="text-right">Screenshot</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredLogs.map((log) => (
                <TableRow key={log.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-mono text-xs text-primary/70">{log.id}</TableCell>
                  <TableCell className="font-medium text-sm">{log.campaign_name || "-"}</TableCell>
                  <TableCell>
                    {log.status === "SUCCESS" && (
                       <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">Sukces</Badge>
                    )}
                    {log.status === "CHECKPOINT_DETECTED" && (
                       <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/20 border-none">Checkpoint</Badge>
                    )}
                    {log.status === "FAILED" && (
                       <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">Błąd</Badge>
                    )}
                    {log.status === "EXCEPTION" && (
                       <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">Wyjątek</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate">{log.error_message || "-"}</TableCell>
                  <TableCell className="text-xs">{log.retry_count}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {log.executed_at ? new Date(log.executed_at).toLocaleString("pl-PL") : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    {log.screenshot_path && (
                      <Button variant="ghost" size="icon" className="text-primary hover:text-primary hover:bg-primary/10">
                        <ImageIcon className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {filteredLogs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Brak logów
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
