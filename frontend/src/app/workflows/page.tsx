"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import {
  Plus, Pencil, Trash2, Play, Pause, Workflow, Loader2,
} from "lucide-react"

interface WorkflowItem {
  id: number
  name: string
  description: string | null
  account_id: number | null
  status: string
  node_count: number
  last_run_status: string | null
  created_at: string
}

const STATUS_BADGES: Record<string, { label: string; variant: string }> = {
  SZKIC: { label: "Szkic", variant: "outline" },
  AKTYWNY: { label: "Aktywny", variant: "default" },
  WSTRZYMANY: { label: "Wstrzymany", variant: "secondary" },
}

const RUN_STATUS_COLORS: Record<string, string> = {
  COMPLETED: "text-emerald-400",
  FAILED: "text-rose-400",
  RUNNING: "text-primary",
  PENDING: "text-muted-foreground",
  CANCELLED: "text-muted-foreground",
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const fetchData = async () => {
    try {
      const data = await api.workflows.list()
      setWorkflows(data)
    } catch (e) {
      console.error("Failed to load workflows:", e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleCreate = async () => {
    try {
      const wf = await api.workflows.create({ name: "Nowy workflow" })
      router.push(`/workflows/editor?id=${wf.id}`)
    } catch (e) {
      console.error("Failed to create workflow:", e)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Usunąć ten workflow?")) return
    try {
      await api.workflows.delete(id)
      setWorkflows((prev) => prev.filter((w) => w.id !== id))
    } catch (e) {
      console.error("Failed to delete workflow:", e)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6 text-primary" />
            Workflows
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Buduj przepływy automatyzacji za pomocą grafu węzłów
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Nowy Workflow
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : workflows.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Workflow className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Brak workflows. Stwórz pierwszy!</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nazwa</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-center">Węzły</TableHead>
                  <TableHead>Ostatni run</TableHead>
                  <TableHead>Utworzono</TableHead>
                  <TableHead className="text-right">Akcje</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {workflows.map((wf) => (
                  <TableRow key={wf.id}>
                    <TableCell>
                      <div>
                        <span className="font-medium">{wf.name}</span>
                        {wf.description && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {wf.description}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_BADGES[wf.status]?.variant as any || "outline"}>
                        {STATUS_BADGES[wf.status]?.label || wf.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">{wf.node_count}</TableCell>
                    <TableCell>
                      {wf.last_run_status ? (
                        <span className={`text-xs ${RUN_STATUS_COLORS[wf.last_run_status] || ""}`}>
                          {wf.last_run_status}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(wf.created_at).toLocaleDateString("pl-PL")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => router.push(`/workflows/editor?id=${wf.id}`)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(wf.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
