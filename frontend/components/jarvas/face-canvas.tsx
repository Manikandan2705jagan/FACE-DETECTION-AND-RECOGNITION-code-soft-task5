"use client";

import * as React from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import type { Detection } from "@/lib/types";

export function FaceCanvas({
  src,
  width,
  height,
  detections,
  labels,
  showLandmarks = true,
  className,
}: {
  src: string;
  width: number;
  height: number;
  detections: Detection[];
  labels?: (string | null)[];
  showLandmarks?: boolean;
  className?: string;
}) {
  const [ready, setReady] = React.useState(false);
  const safeW = width || 1;
  const safeH = height || 1;

  return (
    <div className={cn("relative overflow-hidden rounded-xl border border-white/10", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Analyzed upload"
        onLoad={() => setReady(true)}
        className="block h-auto w-full select-none"
      />
      {ready &&
        detections.map((det, i) => {
          const left = (det.bbox.x1 / safeW) * 100;
          const top = (det.bbox.y1 / safeH) * 100;
          const w = ((det.bbox.x2 - det.bbox.x1) / safeW) * 100;
          const h = ((det.bbox.y2 - det.bbox.y1) / safeH) * 100;
          const label = labels?.[i];
          return (
            <motion.div
              key={det.id ?? i}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.08, duration: 0.35 }}
              className="absolute"
              style={{ left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%` }}
            >
              <div className="absolute inset-0 rounded-md ring-2 ring-cyan-400/90" style={{ boxShadow: "0 0 24px -6px rgba(34,211,238,0.9)" }} />
              {label && (
                <div className="absolute -top-7 left-0 max-w-[18rem] truncate rounded-md bg-navy-900/90 px-2 py-1 text-xs font-medium text-cyan-100 ring-1 ring-cyan-400/40">
                  {label}
                </div>
              )}
              <div className="absolute -bottom-6 left-0 rounded bg-navy-900/80 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-200">
                {(det.confidence * 100).toFixed(0)}%
              </div>
              {showLandmarks &&
                det.landmarks?.map(([px, py], li) => (
                  <span
                    key={li}
                    className="absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-300 ring-2 ring-teal-300/40"
                    style={{ left: `${(px / safeW) * 100}%`, top: `${(py / safeH) * 100}%` }}
                  />
                ))}
            </motion.div>
          );
        })}
    </div>
  );
}
