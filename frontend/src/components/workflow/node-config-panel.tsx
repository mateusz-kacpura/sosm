"use client"

import { useCallback, useEffect, useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { X, Calendar, FileText, ImagePlus, Film } from "lucide-react"
import type { Node } from "@xyflow/react"
import type { WorkflowNodeData } from "./nodes/base-node"
import { GroupScheduleModal, type PostGroupsConfig } from "./group-schedule-modal"
import { FB_BACKGROUNDS } from "@/app/campaigns/spreadsheet"
import { api, uploadMedia } from "@/lib/api"

interface NodeConfigPanelProps {
  node: Node<WorkflowNodeData> | null
  accounts: { id: number; fb_email: string }[]
  onUpdate: (nodeId: string, data: Partial<WorkflowNodeData>) => void
  onClose: () => void
}

export function NodeConfigPanel({ node, accounts, onUpdate, onClose }: NodeConfigPanelProps) {
  const [config, setConfig] = useState<Record<string, any>>({})
  const [label, setLabel] = useState("")
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [mediaUploading, setMediaUploading] = useState(false)

  useEffect(() => {
    if (node) {
      setConfig(node.data?.config || {})
      setLabel(node.data?.label || "")
    }
  }, [node])

  const updateField = useCallback(
    (key: string, value: any) => {
      const newConfig = { ...config, [key]: value }
      setConfig(newConfig)
      if (node) onUpdate(node.id, { config: newConfig })
    },
    [config, node, onUpdate],
  )

  const updateLabel = useCallback(
    (value: string) => {
      setLabel(value)
      if (node) onUpdate(node.id, { label: value })
    },
    [node, onUpdate],
  )

  const handleFanpageMedia = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files
    if (!fileList || fileList.length === 0) return
    setMediaUploading(true)
    try {
      const result = await uploadMedia(Array.from(fileList))
      const newNames = (result.files || []).map((f: any) => f.filename)
      const merged = [...(config.media_files || []), ...newNames]
      updateField("media_files", merged)
    } catch (err) {
      console.error("Media upload failed:", err)
    } finally {
      setMediaUploading(false)
      e.target.value = ""
    }
  }, [config, updateField])

  const removeFanpageMedia = useCallback((filename: string) => {
    const updated = (config.media_files || []).filter((f: string) => f !== filename)
    updateField("media_files", updated)
    api.media.delete(filename).catch(() => {})
  }, [config, updateField])

  if (!node) return null

  const type = node.type || ""

  return (
    <div className="w-72 shrink-0 border-l border-primary/10 bg-card overflow-y-auto">
      <div className="flex items-center justify-between p-3 border-b border-primary/10">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Konfiguracja
        </h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-3 space-y-3">
        {/* Common: Label */}
        <div className="space-y-1">
          <Label className="text-xs">Nazwa</Label>
          <Input
            value={label}
            onChange={(e) => updateLabel(e.target.value)}
            className="h-8 text-xs"
          />
        </div>

        {/* Login */}
        {type === "login" && (
          <div className="space-y-1">
            <Label className="text-xs">Konto FB</Label>
            <select
              value={config.account_id || ""}
              onChange={(e) => updateField("account_id", Number(e.target.value) || null)}
              className="w-full h-8 rounded-md border border-input bg-secondary/50 px-2 text-xs"
            >
              <option value="">Wybierz konto...</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>{acc.fb_email}</option>
              ))}
            </select>
          </div>
        )}

        {/* Post on Groups (multi-group with schedule) */}
        {type === "post_group" && (
          <>
            {/* Summary */}
            <div className="space-y-2 border border-primary/10 rounded-lg p-2.5 bg-secondary/30">
              <div className="flex items-center gap-2 text-xs">
                <Calendar className="h-3.5 w-3.5 text-primary" />
                <span className="font-medium">
                  {(config.groups?.length || 0)}{" "}
                  {(config.groups?.length || 0) === 1 ? "grupa" : (config.groups?.length || 0) < 5 ? "grupy" : "grup"}
                </span>
                {(config.groups || []).filter((g: any) => g.recurring).length > 0 && (
                  <span className="text-primary text-[10px]">
                    · {(config.groups || []).filter((g: any) => g.recurring).length} cyklicznych
                  </span>
                )}
              </div>
              {config.default_content && (
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <FileText className="h-3 w-3 mt-0.5 shrink-0" />
                  <span className="truncate">{config.default_content.slice(0, 60)}{config.default_content.length > 60 ? "..." : ""}</span>
                </div>
              )}
              {config.publish_as_fanpage && (
                <div className="flex items-center gap-2 text-[11px] text-primary">
                  <span>👤</span>
                  <span className="truncate">Jako fanpage</span>
                </div>
              )}
              {(config.groups || []).some((g: any) => g.background_style) && (
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>🎨</span>
                  <span>{(config.groups || []).filter((g: any) => g.background_style).length} z tłem</span>
                </div>
              )}
              {(config.default_media_files?.length > 0) && (
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <ImagePlus className="h-3 w-3" />
                  <span>{config.default_media_files.length} {config.default_media_files.length === 1 ? "plik" : "plików"} media</span>
                </div>
              )}
            </div>

            <Button
              size="sm"
              variant="outline"
              className="w-full"
              onClick={() => setShowScheduleModal(true)}
            >
              <Calendar className="h-3.5 w-3.5 mr-1.5" />
              Otwórz harmonogram
            </Button>

            {showScheduleModal && (
              <GroupScheduleModal
                config={{
                  groups: config.groups || [],
                  default_content: config.default_content || "",
                  background_style: config.background_style || "",
                  active_hours_start: config.active_hours_start || "08:00",
                  active_hours_end: config.active_hours_end || "20:00",
                  spread_minutes: config.spread_minutes || 15,
                  publish_as_fanpage: config.publish_as_fanpage || "",
                  default_media_files: config.default_media_files || [],
                }}
                onSave={(newConfig: PostGroupsConfig) => {
                  const merged = {
                    ...config,
                    groups: newConfig.groups,
                    default_content: newConfig.default_content,
                    background_style: newConfig.background_style,
                    active_hours_start: newConfig.active_hours_start,
                    active_hours_end: newConfig.active_hours_end,
                    spread_minutes: newConfig.spread_minutes,
                    publish_as_fanpage: newConfig.publish_as_fanpage,
                    default_media_files: newConfig.default_media_files,
                  }
                  setConfig(merged)
                  if (node) onUpdate(node.id, { config: merged })
                }}
                onClose={() => setShowScheduleModal(false)}
              />
            )}
          </>
        )}

        {/* Post on Fanpage */}
        {type === "post_fanpage" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">URL fanpage</Label>
              <Input
                value={config.fanpage_url || ""}
                onChange={(e) => updateField("fanpage_url", e.target.value)}
                placeholder="https://facebook.com/..."
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Treść posta</Label>
              <textarea
                value={config.content || ""}
                onChange={(e) => updateField("content", e.target.value)}
                className="w-full rounded-md border border-input bg-secondary/50 px-2 py-1.5 text-xs min-h-[60px] resize-y"
              />
              {config.background_style && (
                <p className="text-[10px] text-muted-foreground">Maks. 100 znaków z tłem</p>
              )}
            </div>
            {/* Media upload */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Label className="text-xs flex items-center gap-1">
                  <ImagePlus className="h-3 w-3 text-primary" />
                  Media
                </Label>
                <label className={`text-[10px] cursor-pointer ${mediaUploading ? "text-muted-foreground" : "text-primary hover:text-primary/80"}`}>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime"
                    multiple
                    onChange={handleFanpageMedia}
                    disabled={mediaUploading}
                    className="hidden"
                  />
                  {mediaUploading ? "..." : "+ Dodaj"}
                </label>
              </div>
              {(config.media_files?.length > 0) && (
                <div className="flex flex-wrap gap-1.5">
                  {(config.media_files || []).map((filename: string) => {
                    const isVideo = filename.endsWith(".mp4") || filename.endsWith(".mov")
                    return (
                      <div key={filename} className="relative group">
                        <div className="h-12 w-12 rounded border border-primary/10 bg-secondary/50 flex items-center justify-center overflow-hidden">
                          {isVideo ? (
                            <Film className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ImagePlus className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>
                        <button
                          onClick={() => removeFanpageMedia(filename)}
                          className="absolute -top-1 -right-1 h-3.5 w-3.5 rounded-full bg-rose-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="h-2 w-2" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
              {(config.media_files?.length > 0) && (
                <p className="text-[9px] text-muted-foreground">Media i tło się wykluczają</p>
              )}
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Tło posta</Label>
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => updateField("background_style", "")}
                  className={`h-7 w-7 rounded-md border text-[10px] ${
                    !config.background_style ? "border-primary ring-2 ring-primary/30" : "border-primary/10"
                  } bg-secondary/50`}
                  title="Brak tła"
                >
                  ∅
                </button>
                {FB_BACKGROUNDS.map((bg) => (
                  <button
                    key={bg.id}
                    onClick={() => updateField("background_style", bg.id)}
                    className={`h-7 w-7 rounded-md border ${
                      config.background_style === bg.id
                        ? "border-primary ring-2 ring-primary/30 scale-110"
                        : "border-primary/10"
                    }`}
                    style={{ backgroundColor: bg.color }}
                    title={bg.label}
                  />
                ))}
              </div>
            </div>
          </>
        )}

        {/* Like Page */}
        {type === "like_page" && (
          <div className="space-y-1">
            <Label className="text-xs">URL strony</Label>
            <Input
              value={config.page_url || ""}
              onChange={(e) => updateField("page_url", e.target.value)}
              placeholder="https://facebook.com/..."
              className="h-8 text-xs"
            />
          </div>
        )}

        {/* Comment */}
        {type === "comment" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">URL posta</Label>
              <Input
                value={config.post_url || ""}
                onChange={(e) => updateField("post_url", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Treść komentarza</Label>
              <textarea
                value={config.comment_text || ""}
                onChange={(e) => updateField("comment_text", e.target.value)}
                className="w-full rounded-md border border-input bg-secondary/50 px-2 py-1.5 text-xs min-h-[60px] resize-y"
              />
            </div>
          </>
        )}

        {/* Send Message */}
        {type === "send_message" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">URL profilu</Label>
              <Input
                value={config.profile_url || ""}
                onChange={(e) => updateField("profile_url", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Treść wiadomości</Label>
              <textarea
                value={config.message_text || ""}
                onChange={(e) => updateField("message_text", e.target.value)}
                className="w-full rounded-md border border-input bg-secondary/50 px-2 py-1.5 text-xs min-h-[60px] resize-y"
              />
            </div>
          </>
        )}

        {/* Wait */}
        {type === "wait" && (
          <>
            <div className="flex gap-2">
              <div className="flex-1 space-y-1">
                <Label className="text-xs">Czas</Label>
                <Input
                  type="number"
                  value={config.duration || ""}
                  onChange={(e) => updateField("duration", Number(e.target.value))}
                  className="h-8 text-xs"
                  min={1}
                />
              </div>
              <div className="w-20 space-y-1">
                <Label className="text-xs">Jednostka</Label>
                <select
                  value={config.unit || "s"}
                  onChange={(e) => updateField("unit", e.target.value)}
                  className="w-full h-8 rounded-md border border-input bg-secondary/50 px-2 text-xs"
                >
                  <option value="s">sek</option>
                  <option value="m">min</option>
                  <option value="h">godz</option>
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={config.random_variation || false}
                onChange={(e) => updateField("random_variation", e.target.checked)}
                className="rounded"
              />
              Losowe odchylenie (±20%)
            </label>
          </>
        )}

        {/* If/Else */}
        {type === "if_else" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">Zmienna</Label>
              <Input
                value={config.variable || ""}
                onChange={(e) => updateField("variable", e.target.value)}
                placeholder="np. login_result"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Operator</Label>
              <select
                value={config.operator || "eq"}
                onChange={(e) => updateField("operator", e.target.value)}
                className="w-full h-8 rounded-md border border-input bg-secondary/50 px-2 text-xs"
              >
                <option value="eq">== (równe)</option>
                <option value="neq">!= (różne)</option>
                <option value="gt">&gt; (większe)</option>
                <option value="lt">&lt; (mniejsze)</option>
                <option value="contains">zawiera</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Wartość</Label>
              <Input
                value={config.value || ""}
                onChange={(e) => updateField("value", e.target.value)}
                placeholder="np. true, checkpoint"
                className="h-8 text-xs"
              />
            </div>
          </>
        )}

        {/* Loop */}
        {type === "loop" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">Liczba iteracji</Label>
              <Input
                type="number"
                value={config.iterations || ""}
                onChange={(e) => updateField("iterations", Number(e.target.value))}
                className="h-8 text-xs"
                min={1}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Zmienna iteratora</Label>
              <Input
                value={config.iterator_variable || ""}
                onChange={(e) => updateField("iterator_variable", e.target.value)}
                placeholder="np. i"
                className="h-8 text-xs font-mono"
              />
            </div>
          </>
        )}

        {/* Variable */}
        {type === "variable" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">Nazwa zmiennej</Label>
              <Input
                value={config.name || ""}
                onChange={(e) => updateField("name", e.target.value)}
                placeholder="np. group_urls"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Typ</Label>
              <select
                value={config.var_type || "text"}
                onChange={(e) => updateField("var_type", e.target.value)}
                className="w-full h-8 rounded-md border border-input bg-secondary/50 px-2 text-xs"
              >
                <option value="text">Tekst</option>
                <option value="url_list">Lista URL</option>
                <option value="number">Liczba</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Wartość</Label>
              <textarea
                value={config.value || ""}
                onChange={(e) => updateField("value", e.target.value)}
                className="w-full rounded-md border border-input bg-secondary/50 px-2 py-1.5 text-xs min-h-[60px] resize-y font-mono"
                placeholder={config.var_type === "url_list" ? "Jeden URL na linię" : "Wartość..."}
              />
            </div>
          </>
        )}

        {/* Webhook */}
        {type === "webhook" && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">URL</Label>
              <Input
                value={config.url || ""}
                onChange={(e) => updateField("url", e.target.value)}
                placeholder="https://..."
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Metoda HTTP</Label>
              <select
                value={config.method || "POST"}
                onChange={(e) => updateField("method", e.target.value)}
                className="w-full h-8 rounded-md border border-input bg-secondary/50 px-2 text-xs"
              >
                <option value="POST">POST</option>
                <option value="GET">GET</option>
                <option value="PUT">PUT</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Body (JSON template)</Label>
              <textarea
                value={config.body_template || ""}
                onChange={(e) => updateField("body_template", e.target.value)}
                className="w-full rounded-md border border-input bg-secondary/50 px-2 py-1.5 text-xs min-h-[60px] resize-y font-mono"
                placeholder='{"text": "{{variable}}"}'
              />
            </div>
          </>
        )}

        {/* Start/End have no config */}
        {(type === "start" || type === "end") && (
          <p className="text-xs text-muted-foreground italic">
            Ten węzeł nie wymaga konfiguracji.
          </p>
        )}
      </div>
    </div>
  )
}
