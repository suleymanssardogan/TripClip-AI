import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full bg-surface border border-border-strong rounded-md px-4 py-3.5",
        "text-text placeholder:text-text-tertiary text-sm",
        "focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-colors",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
