import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export function Card({ className, hover = false, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface overflow-hidden",
        hover && "transition-all hover:border-border-strong hover:-translate-y-0.5",
        className
      )}
      {...props}
    />
  );
}
