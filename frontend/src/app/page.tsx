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

async function getStats() {
  // W przyszłości pobieranie z API
  return {
    activeCampaigns: 2,
    totalAccounts: 5,
    postsToday: 12,
    successRate: "98%"
  }
}

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])

  useEffect(() => {
    // Symulacja pobierania danych z API FastAPI
    setStats({
      activeCampaigns: 3,
      totalAccounts: 4,
      postsToday: 24,
      successRate: "95%"
    })

    setLogs([
      { id: 1, account: "user1@fb.com", group: "Giełda Warszawa", status: "SUCCESS", time: "10:15" },
      { id: 2, account: "user2@fb.com", group: "Programiści PL", status: "SUCCESS", time: "09:45" },
      { id: 3, account: "user1@fb.com", group: "Sprzedam/Kupię", status: "FAILED", time: "09:12", error: "Checkpoint detected" },
      { id: 4, account: "user3@fb.com", group: "Marketing 2024", status: "SUCCESS", time: "08:30" },
    ])
  }, [])

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
            <div className="text-2xl font-bold">{stats.activeCampaigns}</div>
            <p className="text-xs text-muted-foreground">+1 od wczoraj</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Konta Facebook</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalAccounts}</div>
            <p className="text-xs text-muted-foreground">Wszystkie aktywne</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Posty (Dzisiaj)</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.postsToday}</div>
            <p className="text-xs text-muted-foreground">Cel: 30</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Skuteczność</CardTitle>
            <Activity className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.successRate}</div>
            <div className="h-1.5 w-full bg-secondary mt-2 rounded-full overflow-hidden">
               <div className="h-full bg-primary" style={{ width: stats.successRate }}></div>
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
                <TableHead>Konto</TableHead>
                <TableHead>Grupa</TableHead>
                <TableHead>Czas</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium">{log.account}</TableCell>
                  <TableCell>{log.group}</TableCell>
                  <TableCell className="text-muted-foreground">{log.time}</TableCell>
                  <TableCell>
                    {log.status === "SUCCESS" ? (
                      <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">
                        <CheckCircle2 className="mr-1 h-3 w-3" /> Sukces
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">
                        <AlertCircle className="mr-1 h-3 w-3" /> Błąd
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
