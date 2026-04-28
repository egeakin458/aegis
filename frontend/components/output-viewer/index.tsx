'use client'
import { useState } from 'react'
import { X, Download, ChevronRight, ChevronDown, FileCode } from 'lucide-react'
import type { OutputManifest, OutputFile } from '@/lib/types/api'

interface Props {
  manifest: OutputManifest | null
  runId: string | null
  open: boolean
  onClose: () => void
}

interface TreeNode {
  name: string
  path: string
  file?: OutputFile
  children: Record<string, TreeNode>
}

function buildTree(files: OutputFile[]): TreeNode {
  const root: TreeNode = { name: '', path: '', children: {} }
  for (const file of files) {
    const parts = file.path.split('/')
    let node = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (!node.children[part]) {
        node.children[part] = { name: part, path: parts.slice(0, i + 1).join('/'), children: {} }
      }
      node = node.children[part]
      if (i === parts.length - 1) node.file = file
    }
  }
  return root
}

function TreeNodeRow({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selected: string | null
  onSelect: (file: OutputFile) => void
}) {
  const [open, setOpen] = useState(true)
  const isDir = !node.file
  const isSelected = selected === node.path

  if (isDir && Object.keys(node.children).length === 0) return null

  return (
    <div>
      <button
        onClick={() => (isDir ? setOpen(o => !o) : onSelect(node.file!))}
        className={`flex items-center gap-1.5 w-full text-left px-2 py-1 rounded text-xs transition-colors
          ${isSelected ? 'bg-aegis-accent/20 text-aegis-accent' : 'text-slate-300 hover:bg-slate-800'}`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {isDir
          ? (open ? <ChevronDown size={12} className="shrink-0 text-slate-500" /> : <ChevronRight size={12} className="shrink-0 text-slate-500" />)
          : <FileCode size={12} className="shrink-0 text-slate-500" />}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && open && Object.values(node.children).map(child => (
        <TreeNodeRow key={child.path} node={child} depth={depth + 1} selected={selected} onSelect={onSelect} />
      ))}
    </div>
  )
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export function OutputViewer({ manifest, runId, open, onClose }: Props) {
  const [selectedFile, setSelectedFile] = useState<OutputFile | null>(null)

  if (!open) return null

  const tree = manifest ? buildTree(manifest.files) : null
  const downloadUrl = runId ? `${BASE_URL}/api/pipeline/${runId}/output/download` : '#'

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/50" onClick={onClose} />

      {/* Drawer */}
      <div className="w-[680px] bg-[#0f172a] border-l border-slate-800 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <span className="text-sm font-semibold text-slate-200">Generated Files</span>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              download
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
            >
              <Download size={13} />
              Download ZIP
            </a>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* File tree */}
          <div className="w-56 shrink-0 border-r border-slate-800 overflow-y-auto py-2">
            {tree && Object.values(tree.children).map(child => (
              <TreeNodeRow
                key={child.path}
                node={child}
                depth={0}
                selected={selectedFile?.path ?? null}
                onSelect={setSelectedFile}
              />
            ))}
            {!manifest && (
              <p className="text-xs text-slate-600 px-3 py-2">Loading...</p>
            )}
          </div>

          {/* File content */}
          <div className="flex-1 overflow-auto p-4">
            {selectedFile ? (
              <>
                <p className="text-xs text-slate-500 mb-2 font-mono">{selectedFile.path}</p>
                {selectedFile.content ? (
                  <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
                    {selectedFile.content}
                  </pre>
                ) : (
                  <p className="text-xs text-slate-500 italic">File too large to preview.</p>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-600 mt-8 text-center">Select a file to view its contents.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
