"use client"

import { useCallback, useRef, useState } from "react"
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type ReactFlowInstance,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"

import { nodeTypes, type WorkflowNodeData } from "./nodes/base-node"
import { NodePalette, DEFAULT_LABELS } from "./node-palette"
import { NodeConfigPanel } from "./node-config-panel"

interface WorkflowCanvasProps {
  initialNodes: Node<WorkflowNodeData>[]
  initialEdges: Edge[]
  initialViewport?: { x: number; y: number; zoom: number }
  accounts: { id: number; fb_email: string; fanpages: { id: number; fanpage_url: string; fanpage_name: string | null }[] }[]
  onSave: (nodes: Node[], edges: Edge[], viewport: { x: number; y: number; zoom: number }) => void
  nodeStatuses?: Record<string, string>  // nodeId → status (for live run overlay)
}

let nodeIdCounter = 0

export function WorkflowCanvas({
  initialNodes,
  initialEdges,
  initialViewport,
  accounts,
  onSave,
  nodeStatuses,
}: WorkflowCanvasProps) {
  const [nodes, setNodes] = useState<Node<WorkflowNodeData>[]>(() => {
    // Apply statuses if provided
    if (nodeStatuses) {
      return initialNodes.map((n) => ({
        ...n,
        data: { ...n.data, status: nodeStatuses[n.id] as any },
      }))
    }
    return initialNodes
  })
  const [edges, setEdges] = useState<Edge[]>(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node<WorkflowNodeData> | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)

  // All handlers memoized (React 19 + @xyflow/react safety)
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds) as Node<WorkflowNodeData>[]),
    [],
  )

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const onConnect: OnConnect = useCallback(
    (connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            animated: false,
            style: { stroke: "var(--primary)", strokeWidth: 2, strokeOpacity: 0.4 },
          },
          eds,
        ),
      )
    },
    [],
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node as Node<WorkflowNodeData>)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = "move"
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const nodeType = event.dataTransfer.getData("application/reactflow-type")
      const label = event.dataTransfer.getData("application/reactflow-label")

      if (!nodeType || !rfInstance || !reactFlowWrapper.current) return

      const position = rfInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      nodeIdCounter++
      const newNode: Node<WorkflowNodeData> = {
        id: `node_${Date.now()}_${nodeIdCounter}`,
        type: nodeType,
        position,
        data: {
          label: label || DEFAULT_LABELS[nodeType] || nodeType,
          config: {},
        },
      }

      setNodes((nds) => [...nds, newNode])
    },
    [rfInstance],
  )

  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Partial<WorkflowNodeData>) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n
          return { ...n, data: { ...n.data, ...data } }
        }),
      )
      // Update selected node reference
      setSelectedNode((prev) => {
        if (prev && prev.id === nodeId) {
          return { ...prev, data: { ...prev.data, ...data } }
        }
        return prev
      })
    },
    [],
  )

  const handleSave = useCallback(() => {
    if (!rfInstance) return
    const viewport = rfInstance.getViewport()
    onSave(nodes, edges, viewport)
  }, [rfInstance, nodes, edges, onSave])

  // Keyboard shortcuts
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "s") {
        event.preventDefault()
        handleSave()
      }
    },
    [handleSave],
  )

  return (
    <div className="flex h-full" onKeyDown={onKeyDown} tabIndex={0}>
      <NodePalette />

      <div className="flex-1 relative" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onInit={setRfInstance}
          nodeTypes={nodeTypes}
          defaultViewport={initialViewport || { x: 0, y: 0, zoom: 1 }}
          fitView={!initialViewport}
          deleteKeyCode="Delete"
          multiSelectionKeyCode="Shift"
          snapToGrid
          snapGrid={[15, 15]}
          proOptions={{ hideAttribution: true }}
        >
          <Controls showInteractive={false} />
          <MiniMap
            nodeStrokeWidth={3}
            pannable
            zoomable
          />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        </ReactFlow>

        {/* Save button */}
        <div className="absolute top-3 right-3 z-10">
          <button
            onClick={handleSave}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground
                       hover:bg-primary/90 transition-colors shadow-lg"
          >
            Zapisz (Ctrl+S)
          </button>
        </div>
      </div>

      {selectedNode && (
        <NodeConfigPanel
          node={selectedNode}
          accounts={accounts}
          onUpdate={handleNodeUpdate}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}
