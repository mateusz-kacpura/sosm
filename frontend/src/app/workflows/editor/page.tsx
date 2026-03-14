"use client"

import { useEffect, useState, useCallback, Suspense } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { WorkflowCanvas } from "@/components/workflow/workflow-canvas"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ArrowLeft, Play, Loader2, Save } from "lucide-react"
import type { Node, Edge } from "@xyflow/react"
import type { WorkflowNodeData } from "@/components/workflow/nodes/base-node"

function WorkflowEditorInner() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const workflowId = Number(searchParams.get("id"))

  const [workflow, setWorkflow] = useState<any>(null)
  const [accounts, setAccounts] = useState<{ id: number; fb_email: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState("")
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!workflowId) return
    Promise.all([
      api.workflows.get(workflowId),
      api.accounts.list(),
    ]).then(([wf, accs]) => {
      setWorkflow(wf)
      setName(wf.name)
      setAccounts(accs)
      setLoading(false)
    }).catch((e) => {
      console.error("Failed to load workflow:", e)
      setLoading(false)
    })
  }, [workflowId])

  // Poll active run status
  useEffect(() => {
    if (!activeRunId || !workflowId) return

    const interval = setInterval(async () => {
      try {
        const run = await api.workflows.getRun(workflowId, activeRunId)
        const nodeExecs = await api.workflows.getRunNodes(workflowId, activeRunId)

        const statuses: Record<string, string> = {}
        for (const ne of nodeExecs) {
          statuses[ne.node_id] = ne.status.toLowerCase()
        }
        setNodeStatuses(statuses)

        if (run.status === "COMPLETED" || run.status === "FAILED" || run.status === "CANCELLED") {
          setActiveRunId(null)
        }
      } catch (e) {
        console.error("Failed to poll run status:", e)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [activeRunId, workflowId])

  const handleSave = useCallback(
    async (nodes: Node[], edges: Edge[], viewport: { x: number; y: number; zoom: number }) => {
      setSaving(true)
      try {
        await api.workflows.update(workflowId, {
          name,
          graph_data: { nodes, edges, viewport },
        })
      } catch (e) {
        console.error("Failed to save workflow:", e)
      } finally {
        setSaving(false)
      }
    },
    [workflowId, name],
  )

  const handleRun = async () => {
    try {
      const run = await api.workflows.run(workflowId)
      setActiveRunId(run.id)
      setNodeStatuses({})
    } catch (e) {
      console.error("Failed to start run:", e)
    }
  }

  const handleNameBlur = async () => {
    if (name !== workflow?.name) {
      try {
        await api.workflows.update(workflowId, { name })
      } catch (e) {
        console.error("Failed to update name:", e)
      }
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (!workflow) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
        <p className="text-muted-foreground">Workflow nie znaleziony</p>
      </div>
    )
  }

  const graphData = workflow.graph_data || { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-primary/10 bg-card shrink-0">
        <Button variant="ghost" size="sm" onClick={() => router.push("/workflows")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={handleNameBlur}
          className="h-8 w-64 text-sm font-medium"
        />

        <div className="flex-1" />

        {saving && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Zapisywanie...
          </span>
        )}

        {activeRunId && (
          <span className="text-xs text-primary flex items-center gap-1 animate-pulse">
            <Loader2 className="h-3 w-3 animate-spin" /> Wykonywanie...
          </span>
        )}

        <Button size="sm" variant="outline" onClick={handleRun} disabled={!!activeRunId}>
          <Play className="h-3.5 w-3.5 mr-1.5" />
          Uruchom
        </Button>
      </div>

      {/* Canvas */}
      <div className="flex-1 min-h-0">
        <WorkflowCanvas
          initialNodes={graphData.nodes}
          initialEdges={graphData.edges}
          initialViewport={graphData.viewport}
          accounts={accounts}
          onSave={handleSave}
          nodeStatuses={activeRunId ? nodeStatuses : undefined}
        />
      </div>
    </div>
  )
}

export default function WorkflowEditorPage() {
  return (
    <Suspense
      fallback={
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      }
    >
      <WorkflowEditorInner />
    </Suspense>
  )
}
