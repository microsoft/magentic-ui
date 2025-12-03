# shadcn/ui Components

This directory contains **shadcn/ui** primitive components. These are **generated code**, not a library.

## Quick Reference

### Adding a New Component

For a full list of shadcn/ui components, see: [shadcn/ui Components](https://ui.shadcn.com/docs/components)

```bash
cd frontend
pnpm dlx shadcn@latest add <component-name>

# Examples:
pnpm dlx shadcn@latest add dialog
pnpm dlx shadcn@latest add dropdown-menu
```

The CLI reads `components.json` and generates the component in this folder.

### Should I Modify These Files?

**Generally, no.** Follow this priority order:

1. **Use `variant` and `size` props** — Built-in customization

   ```tsx
   <Button variant="secondary" size="sm">
     Click
   </Button>
   ```

2. **Add `className` for one-off styling** — Context-specific overrides

   ```tsx
   <Button className="rounded-full">Pill Button</Button>
   ```

3. **Modify `index.css` design tokens** — App-wide style changes

   ```css
   /* Change primary color for the entire app */
   --primary: var(--color-fuchsia-600);
   ```

4. **Edit component file** — Only when design system itself changes
   - Rare: When Figma design system components are updated
   - Example: Adding a new `variant` that will be used across the app

### Do NOT

- Add business logic to these files
- Import app-specific code (stores, hooks, API)
- Create one-off variants for a single use case

---

## The `cn()` Utility

All components use `cn()` from `@/lib/utils` to merge class names:

```tsx
import { cn } from '@/lib/utils'

// Basic usage - merge multiple classes
<div className={cn('base-class', 'additional-class')} />

// Conditional classes
<div className={cn('base', isActive && 'bg-primary')} />

// Override component defaults via className prop
<Button className="rounded-full" />  // overrides default rounded-md
```

`cn()` is a wrapper around `clsx` + `tailwind-merge`. It:

- Concatenates class names
- Handles conditionals (`false`, `null`, `undefined` are ignored)
- **Resolves Tailwind conflicts** — later classes override earlier ones

---

## Design Tokens

Colors and styles are defined in `src/index.css`. Components use CSS variables like `bg-primary`, `text-foreground`, `border-border`.

### Always Use Semantic Colors

```tsx
// ✅ Good - uses semantic tokens, works with light/dark themes
<div className="bg-card text-card-foreground border-border" />
<Button className="bg-primary text-primary-foreground" />

// ❌ Bad - hardcoded Tailwind colors, breaks theming
<div className="bg-neutral-100 text-neutral-900 border-neutral-300" />
```

Semantic colors automatically adapt to light/dark mode. Raw Tailwind colors don't.

### Token Categories

| Category     | Example                             | Use Case                              |
| ------------ | ----------------------------------- | ------------------------------------- |
| **General**  | `--primary`, `--background`         | Default choice for most cases         |
| **Specific** | `--card`, `--sidebar`, `--popover`  | Use when inside that component type   |
| **Extended** | `--accent-0` to `--accent-3`        | When General tokens have low contrast |
| **Status**   | `--status-active`, `--status-error` | Session/task status indicators        |

### When to Use Extended Tokens

If the default `--accent` causes poor contrast (e.g., text too light on hover background), try `--accent-0` through `--accent-3`:

```tsx
// Default accent might be too similar to background
<div className="bg-accent">...</div>

// Use accent-2 for better contrast
<div className="bg-accent-2">...</div>
```

---

## Component Conventions

**Prefer shadcn/ui primitives over custom implementations.**

For basic UI elements (Button, Card, Dialog, Tooltip, etc.), always use shadcn/ui components. They provide:

- Consistent styling with our design system
- Built-in accessibility (keyboard nav, ARIA, focus management)
- Radix UI primitives (portals, collision detection)

Only create custom components when shadcn/ui doesn't have what you need.

### Button

Always use `<Button>` for clickable elements (never plain `<button>`).

```tsx
// Icon + Text: use gap-2
<Button className="gap-2 rounded-full">
  <Plus className="size-4" />
  New Session
</Button>

// Icon-only: must have aria-label + Tooltip
<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="secondary" size="icon" aria-label="Settings">
      <Settings className="size-4" />
    </Button>
  </TooltipTrigger>
  <TooltipContent>Settings</TooltipContent>
</Tooltip>
```

### Card

For compact/interactive cards, skip `CardHeader`/`CardContent` wrappers:

```tsx
<Card className="hover:bg-card-hover transition-colors">
  <div className="flex flex-col gap-3 p-4">{/* Custom layout */}</div>
</Card>
```

---

## Resources

- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Project Coding Guidelines](/.github/frontend/docs/frontend-coding-guidelines.md)
- [Design Tokens in index.css](../../../index.css)
