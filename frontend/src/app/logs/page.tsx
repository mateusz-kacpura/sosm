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
import { Button } from "@/components/ui/button"
import { 
  History, 
  CheckCircle2, 
  AlertCircle, 
  Image as ImageIcon,
  ExternalLink,
  Search
} from "lucide-react"
import { Input } from "@/components/ui/input"

export default function LogsPage() {
  const [logs, setLogs] = useState<any[]>([])

  useEffect(() => {
    // Symulacja danych historycznych
    setLogs([
      { id: 101, account: "user1@fb.com", group: "Giełda Warszawa", status: "SUCCESS", message: "Opublikowano pomyślnie", date: "2024-03-11 10:15:02" },
      { id: 102, account: "user2@fb.com", group: "Programiści PL", status: "SUCCESS", message: "Opublikowano pomyślnie", date: "2024-03-11 09:45:11" },
      { id: 103, account: "user1@fb.com", group: "Sprzedam/Kupię", status: "CHECKPOINT", message: "Wykryto weryfikację tożsamości", date: "2024-03-11 09:12:45", screenshot: true },
      { id: 104, account: "user3@fb.com", group: "Marketing 2024", status: "SUCCESS", message: "Opublikowano pomyślnie", date: "2024-03-11 08:30:22" },
      { id: 105, account: "user2@fb.com", group: "Freelance PL", status: "FAILED", message: "Brak pola tekstowego (brak uprawnień grupach)", date: "2024-03-11 08:15:00" },
    ])
  }, [])

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
             <Input placeholder="Szukaj po koncie lub grupie..." className="pl-8 bg-secondary/50 border-primary/10" />
           </div>
        </div>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead className="w-[100px]">ID</TableHead>
                <TableHead>Konto / Grupa</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Szczegóły</TableHead>
                <TableHead>Data i Czas</TableHead>
                <TableHead className="text-right">Screenshot</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-mono text-xs text-primary/70">{log.id}</TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                       <span className="font-medium text-sm">{log.account}</span>
                       <span className="text-[11px] text-muted-foreground">{log.group}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {log.status === "SUCCESS" && (
                       <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/20 border-none">Sukces</Badge>
                    )}
                    {log.status === "CHECKPOINT" && (
                       <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/20 border-none">Checkpoint</Badge>
                    )}
                    {log.status === "FAILED" && (
                       <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/20 border-none">Błąd</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate">{log.message}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{log.date}</TableCell>
                  <TableCell className="text-right">
                    {log.screenshot && (
                      <Button variant="ghost" size="icon" className="text-primary hover:text-primary hover:bg-primary/10">
                        <ImageIcon className="h-4 w-4" />
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" className="text-muted-foreground">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
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
