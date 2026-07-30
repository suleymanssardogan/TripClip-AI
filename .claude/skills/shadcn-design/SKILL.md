---
name: shadcn-design
description: TripClip web frontend design direction — shadcn/ui component conventions (Radix primitives, CVA variants, copy-in components) layered on top of TripClip's existing design-system v2 tokens. Use whenever building or restyling UI in web/ (new components, pages, forms, dialogs, dashboards) so new work matches shadcn's structural conventions and ui.shadcn.com's restrained visual voice without discarding TripClip's own amber/teal token system.
metadata:
  scope: project
  version: "1.0.0"
---

# TripClip Web Design Direction (shadcn/ui-based)

Reference: https://ui.shadcn.com/docs and https://ui.shadcn.com/llms.txt

TripClip already has a shipped design system (`web/src/app/globals.css` +
`web/tailwind.config.ts` — "design system v2", self-hosted fonts, CSS-var
tokens). This skill does **not** replace it. It adopts shadcn/ui's
*structural* conventions (how components are built and composed) and
ui.shadcn.com's *visual restraint* (how much whitespace, how loud the
chrome is), while keeping TripClip's actual brand tokens — dark-first,
warm amber accent, teal route color, Satoshi/General Sans type.

Never introduce shadcn's default zinc/slate palette or Inter/Geist font
stack into TripClip. Map onto the existing tokens instead (table below).

## Token mapping

Use these Tailwind classes/CSS vars — already defined, do not invent new
color values or hardcode hex/rgb in component files.

| shadcn concept       | TripClip equivalent                          |
|-----------------------|-----------------------------------------------|
| `background`          | `bg-bg` (`--c-bg`)                             |
| `card`                | `bg-surface` (`--c-surface`), `bg-surface2` for nested/hover |
| `border`               | `border-border`, `border-border-strong` for emphasis |
| `foreground`          | `text-text`                                    |
| `muted-foreground`    | `text-text-secondary` / `text-text-tertiary`   |
| `primary`             | `bg-accent` / `text-accent-text`, hover → `accent-hover`, on-fill text → `on-accent` |
| `secondary accent`    | `text-route` / `bg-route` (teal — used for routes/tags, see `.tag`, `.glow-dot` in globals.css) |
| `destructive`         | `text-destructive` / `bg-destructive`          |
| `success` / `warning` | `text-success`, `text-warning`                 |
| `radius` scale        | Tailwind `rounded-xs|sm|md|lg|xl` as configured (6/10/14/20/28px), not shadcn's default `--radius` |
| `font-sans`           | already `General Sans` (body) / `Satoshi` (display) via `font-sans`/`font-display`, not Geist/Inter |
| card shadow           | `shadow-card` utility (already defined) instead of shadcn's default shadow scale |

All tokens are RGB triplets consumed via `rgb(var(--c-x) / <alpha-value>)`,
so opacity modifiers work normally: `bg-accent/10`, `text-route/60`, etc.
Both `:root.dark` and `:root.light` are defined — new components must
look correct in both without extra dark: variants, since the toggle
(`ThemeToggle.tsx`) swaps the `.light` class on `<html>`, not Tailwind's
`dark:` media strategy.

## Component conventions

- New reusable UI primitives go in `web/src/components/ui/` (does not
  exist yet — create it on first use), one component per file, PascalCase
  filename, following shadcn's shape: a typed props interface, `cn()` for
  class composition, and `class-variance-authority` (`cva`) for
  variant/size props when a component has more than one visual variant.
- `clsx` and `tailwind-merge` are already installed but unused. Before
  the first `ui/` component, add `web/src/lib/utils.ts`:
  ```ts
  import { clsx, type ClassValue } from "clsx";
  import { twMerge } from "tailwind-merge";

  export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
  }
  ```
- Only pull in a Radix primitive (`@radix-ui/react-*`) when a component
  actually needs unstyled accessible behavior (dialog, dropdown, select,
  tooltip, tabs). Copy the component in — don't run the shadcn CLI
  (`npx shadcn add`), since it scaffolds its own `--radius`/zinc tokens
  and a `components.json` that would fight the existing token setup.
- Existing bespoke components (`Navbar.tsx`, `MapPreview.tsx`,
  `AIStatsCard.tsx`, `QRShareCard.tsx`, `PasswordInput.tsx`,
  `ThemeToggle.tsx`) stay as-is; only new/rebuilt UI should follow this
  convention. Don't retrofit working components just to match the
  pattern.

## Visual voice (from ui.shadcn.com itself)

The shadcn docs site is intentionally quiet: hairline 1px borders, a lot
of unused space, restrained type-weight hierarchy (one bold heading, rest
regular), almost no motion beyond a fade/slide on mount, no gradients or
glow by default. Apply that restraint to new TripClip surfaces:

- Prefer `border-border` hairlines over heavy `shadow-card` for
  separating content; reserve `shadow-card` for elevated surfaces
  (modals, popovers, the existing card treatment).
- Default to static, calm components. TripClip's existing accent
  animations (`animate-float`, `animate-glow-pulse`, `animate-pulse-ring`,
  `shimmer`) are reserved for the marketing/landing surfaces that already
  use them — don't add new ambient motion to dashboards, forms, or data
  tables just because it's available in the Tailwind config.
- Respect `prefers-reduced-motion` (already global in `globals.css`) —
  any new animation must be covered by that existing rule, not exempted.
- Generous padding over dense chrome — shadcn components default to
  `p-4`/`p-6` and `gap-4`; match that rather than tightening spacing to
  fit more on screen.

## When this skill does not apply

- iOS (`TripClipApp`, `TripClipShare`) — SwiftUI, unrelated to this stack.
- BFF/core-api responses — this skill is web-frontend visual/component
  design only, not API contracts.
