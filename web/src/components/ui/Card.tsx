import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export function Card({ className, hover = false, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface overflow-hidden shadow-[0_8px_28px_-24px_rgba(24,37,49,0.35)]",
        hover && "transition-all duration-200 hover:border-accent/40 hover:shadow-[0_14px_35px_-25px_rgba(24,37,49,0.3)]",
        className
      )}
      {...props}
    />
  );
}
