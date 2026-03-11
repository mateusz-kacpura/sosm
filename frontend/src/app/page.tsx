"use client"

import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
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
import {
  Activity,
  Users,
  Megaphone,
  CheckCircle2,
  Clock,
  AlertCircle
} from "lucide-react"
import { api } from "@/lib/api"

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, logsData] = await Promise.all([
          api.stats(),
          api.logs.list(),
        ])
        setStats(statsData)
        setLogs(logsData.slice(0, 10))
      } catch (err: any) {
        setError(err.message)
      }
    }
    fetchData()
  }, [])

  if (error) return <div className="text-rose-500">Błąd: {error}</div>
  if (!stats) return <div className="text-primary italic animate-pulse">Ładowanie statystyk...</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h2>
        <p className="text-muted-foreground">Witaj w systemie SOSM Automation.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktywne Kampanie</CardTitle>
            <Megaphone className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.active_campaigns}</div>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Konta Facebook</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_accounts}</div>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Posty (Dzisiaj)</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.posts_today}</div>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Skuteczność</CardTitle>
            <Activity className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.success_rate}</div>
            <div className="h-1.5 w-full bg-secondary mt-2 rounded-full overflow-hidden">
               <div className="h-full bg-primary" style={{ width: stats.success_rate }}></div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardHeader>
          <CardTitle>Ostatnie Aktywności</CardTitle>
          <CardDescription>Lista 10 najnowszych prób publikacji w grupach.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead>Kampania</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Czas</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium">{log.campaign_name || "-"}</TableCell>
                  <TableCell>
                    {log.status === "SUCCESS" ? (
                      <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">
                        <CheckCircle2 className="mr-1 h-3 w-3" /> Sukces
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">
                        <AlertCircle className="mr-1 h-3 w-3" /> {log.status}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {log.executed_at ? new Date(log.executed_at).toLocaleString("pl-PL") : "-"}
                  </TableCell>
                </TableRow>
              ))}
              {logs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
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
