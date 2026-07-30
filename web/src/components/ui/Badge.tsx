import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const badgeVariants = cva(
  "inline-flex items-center font-mono text-[9px] px-2 py-1 rounded-full uppercase tracking-widest",
  {
    variants: {
      variant: {
        success: "bg-success/10 border border-success/25 text-success",
        warning: "bg-warning/10 border border-warning/25 text-warning",
        route: "bg-route/10 border border-route/25 text-route",
        neutral: "bg-surface2 border border-border text-text-secondary",
        destructive: "bg-destructive/10 border border-destructive/25 text-destructive",
      },
    },
    defaultVariants: { variant: "neutral" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
