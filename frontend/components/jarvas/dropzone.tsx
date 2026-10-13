"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { FileUp, UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatBytes } from "@/lib/utils";

export function Dropzone({
  accept,
  onFile,
  disabled,
  hint,
  className,
}: {
  accept: string;
  onFile: (file: File) => void;
  disabled?: boolean;
  hint?: string;
  className?: string;
}) {
  const [dragging, setDragging] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    onFile(files[0]);
  };

  return (
    <motion.div
      whileHover={disabled ? undefined : { scale: 1.005 }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      className={cn(
        "group relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-10 text-center transition-all",
        dragging ? "border-cyan-400/70 bg-cyan-500/[0.08]" : "border-white/15 bg-white/[0.02] hover:border-indigo-400/50 hover:bg-white/[0.04]",
        disabled && "pointer-events-none opacity-50",
        className,
      )}
    >
      <motion.div
        animate={dragging ? { scale: 1.08, rotate: -3 } : { scale: 1, rotate: 0 }}
        className="rounded-2xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 p-4"
      >
        {dragging ? (
          <FileUp className="h-7 w-7 text-cyan-300" />
        ) : (
          <UploadCloud className="h-7 w-7 text-indigo-300" />
        )}
      </motion.div>
      <div>
        <p className="text-sm font-medium">
          {dragging ? "Drop to upload" : "Drag & drop, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {hint ?? accept.split(",").join(" · ")}
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </motion.div>
  );
}

export function FileChip({ file, onClear }: { file: File; onClear?: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm">
      <span className="truncate">{file.name}</span>
      <span className="ml-3 shrink-0 text-xs text-muted-foreground">{formatBytes(file.size)}</span>
      {onClear && (
        <button onClick={onClear} className="ml-3 text-xs text-muted-foreground hover:text-foreground">
          Clear
        </button>
      )}
    </div>
  );
}
