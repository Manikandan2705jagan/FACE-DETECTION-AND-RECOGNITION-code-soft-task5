import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-indigo-500/20 text-indigo-200",
        secondary: "border-white/10 bg-white/[0.06] text-foreground/80",
        success: "border-transparent bg-teal-500/20 text-teal-200",
        warning: "border-transparent bg-amber-500/20 text-amber-200",
        destructive: "border-transparent bg-rose-500/20 text-rose-200",
        outline: "border-white/15 text-foreground/80",
        cyan: "border-transparent bg-cyan-500/20 text-cyan-200",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
