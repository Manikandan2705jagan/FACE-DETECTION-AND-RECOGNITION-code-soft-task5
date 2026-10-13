"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

export function PrivacyBanner({
  children,
  className,
  icon,
  tone = "info",
}: {
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
  tone?: "info" | "warning" | "neutral";
}) {
  const tones = {
    info: "border-cyan-500/25 bg-cyan-500/[0.07] text-cyan-50",
    warning: "border-amber-500/25 bg-amber-500/[0.07] text-amber-50",
    neutral: "border-white/10 bg-white/[0.04] text-foreground/80",
  };
  return (
    <div className={cn("flex items-start gap-3 rounded-xl border px-4 py-3 text-sm", tones[tone], className)}>
      <span className="mt-0.5 shrink-0 text-cyan-300">{icon ?? <ShieldCheck className="h-4 w-4" />}</span>
      <div className="leading-relaxed">{children}</div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  accent = "indigo",
  index = 0,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  accent?: "indigo" | "cyan" | "teal" | "amber";
  index?: number;
}) {
  const accents = {
    indigo: "from-indigo-500/25 to-indigo-500/0 text-indigo-300",
    cyan: "from-cyan-500/25 to-cyan-500/0 text-cyan-300",
    teal: "from-teal-500/25 to-teal-500/0 text-teal-300",
    amber: "from-amber-500/25 to-amber-500/0 text-amber-300",
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
    >
      <Card className="relative overflow-hidden">
        <div className={cn("pointer-events-none absolute inset-x-0 -top-16 h-32 bg-gradient-to-b blur-2xl", accents[accent])} />
        <CardContent className="relative flex items-center justify-between p-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
            {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
          </div>
          {icon && <div className={cn("rounded-xl bg-white/[0.05] p-2.5", accents[accent].split(" ").pop())}>{icon}</div>}
        </CardContent>
      </Card>
    </motion.div>
  );
}
