"use client"

import { memo, type ReactNode } from "react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { cn } from "@/lib/utils"
import {
  Play, Square, LogIn, FileText, Heart, MessageCircle, Send,
  Clock, GitBranch, Repeat, Shuffle, Merge, Variable, Webhook,
  type LucideIcon,
} from "lucide-react"

// Category colors (oklch-compatible classes)
const CATEGORY_COLORS: Record<string, string> = {
  trigger: "text-emerald-400",
  facebook: "text-blue-400",
  flow: "text-amber-400",
  utility: "text-purple-400",
}

// Node type → icon mapping
const NODE_ICONS: Record<string, LucideIcon> = {
  start: Play,
  end: Square,
  login: LogIn,
  post_group: FileText,
  post_fanpage: FileText,
  like_page: Heart,
  comment: MessageCircle,
  send_message: Send,
  wait: Clock,
  if_else: GitBranch,
  loop: Repeat,
  random_choice: Shuffle,
  merge: Merge,
  variable: Variable,
  webhook: Webhook,
}

// Node type → category
const NODE_CATEGORIES: Record<string, string> = {
  start: "trigger",
  end: "trigger",
  login: "facebook",
  post_group: "facebook",
  post_fanpage: "facebook",
  like_page: "facebook",
  comment: "facebook",
  send_message: "facebook",
  wait: "flow",
  if_else: "flow",
  loop: "flow",
  random_choice: "flow",
  merge: "flow",
  variable: "utility",
  webhook: "utility",
}

export interface WorkflowNodeData {
  label: string
  config: Record<string, any>
  status?: "pending" | "running" | "completed" | "failed" | "skipped"
  [key: string]: unknown
}

interface BaseNodeProps {
  nodeType: string
  data: WorkflowNodeData
  selected: boolean
  children?: ReactNode
  inputs?: number
  outputs?: { id: string; label?: string; position?: "bottom" | "right" }[]
}

function BaseNodeInner({ nodeType, data, selected, children, inputs = 1, outputs }: BaseNodeProps) {
  const Icon = NODE_ICONS[nodeType] || Play
  const category = NODE_CATEGORIES[nodeType] || "trigger"
  const iconColor = CATEGORY_COLORS[category] || "text-primary"
  const status = data.status

  const defaultOutputs = outputs || [{ id: "default" }]

  return (
    <div
      className={cn(
        "rounded-xl border bg-card text-card-foreground shadow-lg min-w-[180px] max-w-[240px]",
        selected ? "border-primary ring-2 ring-primary/30" : "border-primary/10",
        status === "running" && "border-primary animate-pulse",
        status === "completed" && "border-emerald-500/50",
        status === "failed" && "border-rose-500/50",
        status === "skipped" && "opacity-50",
      )}
    >
      {/* Input handles */}
      {inputs > 0 && nodeType !== "start" && (
        <Handle
          type="target"
          position={Position.Top}
          className="!bg-primary !border-card"
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-primary/5">
        <Icon className={cn("h-4 w-4 shrink-0", iconColor)} />
        <span className="text-xs font-medium truncate">{data.label}</span>
        {status && (
          <span
            className={cn(
              "ml-auto h-2 w-2 rounded-full shrink-0",
              status === "running" && "bg-primary animate-pulse",
              status === "completed" && "bg-emerald-500",
              status === "failed" && "bg-rose-500",
              status === "pending" && "bg-muted-foreground/30",
              status === "skipped" && "bg-muted-foreground/20",
            )}
          />
        )}
      </div>

      {/* Content */}
      {children && (
        <div className="px-3 py-2 text-[11px] text-muted-foreground">
          {children}
        </div>
      )}

      {/* Output handles */}
      {defaultOutputs.map((out, i) => {
        const isRight = out.position === "right"
        return (
          <Handle
            key={out.id}
            type="source"
            position={isRight ? Position.Right : Position.Bottom}
            id={out.id}
            className="!bg-primary !border-card"
            style={
              !isRight && defaultOutputs.filter((o) => o.position !== "right").length > 1
                ? { left: `${((i + 1) * 100) / (defaultOutputs.filter((o) => o.position !== "right").length + 1)}%` }
                : undefined
            }
          />
        )
      })}

      {/* Output labels for multi-output nodes */}
      {defaultOutputs.length > 1 && (
        <div className="flex justify-between px-2 pb-1">
          {defaultOutputs
            .filter((o) => o.label)
            .map((out) => (
              <span key={out.id} className="text-[9px] text-muted-foreground/60">
                {out.label}
              </span>
            ))}
        </div>
      )}
    </div>
  )
}

// ── Concrete node components (all memo'd for React 19 safety) ──

export const StartNode = memo(({ data, selected }: NodeProps) => (
  <BaseNodeInner nodeType="start" data={data as WorkflowNodeData} selected={!!selected} inputs={0} />
))
StartNode.displayName = "StartNode"

export const EndNode = memo(({ data, selected }: NodeProps) => (
  <BaseNodeInner
    nodeType="end"
    data={data as WorkflowNodeData}
    selected={!!selected}
    outputs={[]}
  />
))
EndNode.displayName = "EndNode"

export const LoginNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="login" data={d} selected={!!selected}>
      {d.config?.account_id && <div>Konto #{d.config.account_id}</div>}
    </BaseNodeInner>
  )
})
LoginNode.displayName = "LoginNode"

export const PostGroupNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  const groupCount = d.config?.groups?.length || 0
  const displayContent = d.config?.default_content || d.config?.content || ""
  return (
    <BaseNodeInner nodeType="post_group" data={d} selected={!!selected}>
      {groupCount > 0 && (
        <div>{groupCount} {groupCount === 1 ? "grupa" : groupCount < 5 ? "grupy" : "grup"}</div>
      )}
      {displayContent && (
        <div className="truncate mt-0.5 italic">{displayContent.slice(0, 40)}{displayContent.length > 40 ? "..." : ""}</div>
      )}
      {d.config?.publish_as_fanpage && (
        <div className="truncate text-primary">jako fanpage</div>
      )}
    </BaseNodeInner>
  )
})
PostGroupNode.displayName = "PostGroupNode"

export const PostFanpageNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="post_fanpage" data={d} selected={!!selected}>
      {d.config?.fanpage_url && (
        <div className="truncate">{d.config.fanpage_url}</div>
      )}
    </BaseNodeInner>
  )
})
PostFanpageNode.displayName = "PostFanpageNode"

export const LikePageNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="like_page" data={d} selected={!!selected}>
      {d.config?.page_url && <div className="truncate">{d.config.page_url}</div>}
    </BaseNodeInner>
  )
})
LikePageNode.displayName = "LikePageNode"

export const CommentNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="comment" data={d} selected={!!selected}>
      {d.config?.comment_text && (
        <div className="truncate italic">{d.config.comment_text.slice(0, 40)}</div>
      )}
    </BaseNodeInner>
  )
})
CommentNode.displayName = "CommentNode"

export const SendMessageNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="send_message" data={d} selected={!!selected}>
      {d.config?.profile_url && <div className="truncate">{d.config.profile_url}</div>}
    </BaseNodeInner>
  )
})
SendMessageNode.displayName = "SendMessageNode"

export const WaitNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  const unit = d.config?.unit === "h" ? "godz." : d.config?.unit === "m" ? "min" : "sek"
  return (
    <BaseNodeInner nodeType="wait" data={d} selected={!!selected}>
      {d.config?.duration && <div>{d.config.duration} {unit}</div>}
    </BaseNodeInner>
  )
})
WaitNode.displayName = "WaitNode"

export const IfElseNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner
      nodeType="if_else"
      data={d}
      selected={!!selected}
      outputs={[
        { id: "true", label: "True" },
        { id: "false", label: "False" },
      ]}
    >
      {d.config?.variable && (
        <div>{d.config.variable} {d.config.operator} {d.config.value}</div>
      )}
    </BaseNodeInner>
  )
})
IfElseNode.displayName = "IfElseNode"

export const LoopNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner
      nodeType="loop"
      data={d}
      selected={!!selected}
      outputs={[
        { id: "body", label: "Ciało" },
        { id: "done", label: "Gotowe", position: "right" },
      ]}
    >
      {d.config?.iterations && <div>{d.config.iterations}x iteracji</div>}
    </BaseNodeInner>
  )
})
LoopNode.displayName = "LoopNode"

export const RandomChoiceNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  const count = d.config?.weights?.length || 2
  const outputs = Array.from({ length: count }, (_, i) => ({
    id: `choice_${i}`,
    label: `${i + 1}`,
  }))
  return (
    <BaseNodeInner nodeType="random_choice" data={d} selected={!!selected} outputs={outputs}>
      <div>{count} ścieżek</div>
    </BaseNodeInner>
  )
})
RandomChoiceNode.displayName = "RandomChoiceNode"

export const MergeNode = memo(({ data, selected }: NodeProps) => (
  <BaseNodeInner nodeType="merge" data={data as WorkflowNodeData} selected={!!selected} />
))
MergeNode.displayName = "MergeNode"

export const VariableNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="variable" data={d} selected={!!selected}>
      {d.config?.name && <div className="font-mono">{`{{${d.config.name}}}`}</div>}
    </BaseNodeInner>
  )
})
VariableNode.displayName = "VariableNode"

export const WebhookNode = memo(({ data, selected }: NodeProps) => {
  const d = data as WorkflowNodeData
  return (
    <BaseNodeInner nodeType="webhook" data={d} selected={!!selected}>
      {d.config?.url && <div className="truncate">{d.config.url}</div>}
    </BaseNodeInner>
  )
})
WebhookNode.displayName = "WebhookNode"

// Registry for React Flow
export const nodeTypes = {
  start: StartNode,
  end: EndNode,
  login: LoginNode,
  post_group: PostGroupNode,
  post_fanpage: PostFanpageNode,
  like_page: LikePageNode,
  comment: CommentNode,
  send_message: SendMessageNode,
  wait: WaitNode,
  if_else: IfElseNode,
  loop: LoopNode,
  random_choice: RandomChoiceNode,
  merge: MergeNode,
  variable: VariableNode,
  webhook: WebhookNode,
}
