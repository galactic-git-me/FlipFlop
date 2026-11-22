# FlipFlop Design System - Claude Design System

Premium PC Builder interface using Claude Design System tokens and principles.

## Color Palette

### Primary Surface
- **Surface**: `#0f1419` - Deep charcoal background
- **Surface Alt**: `#1a1f2b` - Cards and panels
- **Surface Raised**: `#242a39` - Elevated elements

### Text
- **Primary**: `#e8eaf0` - Main text
- **Secondary**: `#a0a8c0` - Supporting text
- **Tertiary**: `#7a8299` - Muted text

### Accent (Premium Gold)
- **Primary**: `#d4af37` - CTAs, highlights
- **Hover**: `#e8c547` - Interactive states
- **Dark**: `#c99f2e` - Pressed states

### Status
- **Success**: `#10b981` - Positive actions
- **Error**: `#ef4444` - Alerts
- **Warning**: `#f59e0b` - Cautions
- **Info**: `#3b82f6` - Information

## Typography

### Font Families
- **Serif**: Georgia, Garamond (headings)
- **Sans**: System font stack (body text)
- **Mono**: Monaco, Courier New (code)

### Scale
```css
h1: 2.5rem   (40px)
h2: 2rem     (32px)
h3: 1.5rem   (24px)
h4: 1.25rem  (20px)
body: 1rem   (16px)
```

## Components

### Buttons

**Primary Button** (CTAs)
```tsx
<button className="btn-primary">Continue to Payment</button>
```
- Gold gradient background
- Black text
- 12px × 24px padding
- 8px border-radius
- Hover: shadow lift + glow effect

**Secondary Button** (Alternative actions)
```tsx
<button className="btn-secondary">Edit Configuration</button>
```
- Transparent background
- Gold border on hover
- 10px × 20px padding

### Cards

**Standard Card**
```tsx
<div className="card">Content</div>
```
- Alt surface background
- 1px border
- 12px border-radius
- Hover: gold border + shadow lift

**Raised Card**
```tsx
<div className="card card-raised">Important Content</div>
```
- Raised surface background
- Stronger shadow

### Input Fields

```tsx
<input type="text" placeholder="Budget" />
```
- Alt surface background
- Subtle border
- Gold focus state with glow
- Font size: 0.95rem

### Badges

```tsx
<span className="badge badge-success">In Stock</span>
```

Available: `badge-success`, `badge-error`, `badge-warning`

## Animations

### Duration
- **Fast**: 150ms (quick interactions)
- **Normal**: 300ms (standard transitions)
- **Slow**: 500ms (entrance animations)

### Easing
- **Out**: `cubic-bezier(0.16, 1, 0.3, 1)` (snappy)
- **InOut**: `cubic-bezier(0.4, 0, 0.2, 1)` (smooth)

### Examples

**Hover Lift**
```css
transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
.card:hover { transform: translateY(-2px); }
```

**Color Transition**
```css
a { transition: color 150ms cubic-bezier(0.4, 0, 0.2, 1); }
a:hover { color: var(--color-accent-hover); }
```

## Layout Principles

1. **Dark Luxury**: Deep charcoal foundation with gold accents
2. **Hierarchy**: Use scale, color, and weight for visual hierarchy
3. **Spacing**: Use multiples of 8px for consistency
4. **Depth**: Cards lift on hover, shadows for elevation
5. **Motion**: Purposeful animations that guide attention

## CSS Custom Properties

Use CSS variables for consistency:

```css
/* Colors */
var(--color-surface)
var(--color-accent)
var(--color-text)
var(--color-success)

/* Typography */
var(--font-serif)
var(--font-sans)
var(--font-mono)

/* Animation */
var(--duration-normal)
var(--ease-in-out)
```

## Implementation Checklist

When building components:

- [ ] Use CSS variables for colors (never hardcode)
- [ ] Apply semantic HTML (button, nav, input, etc.)
- [ ] Include hover/focus/active states
- [ ] Use smooth transitions (300ms default)
- [ ] Ensure gold accents on interactive elements
- [ ] Follow 8px spacing grid
- [ ] Test in both light and dark contexts
- [ ] Verify keyboard navigation
- [ ] Check color contrast (WCAG AA minimum)

## Examples

### 3D Configurator Hero
- Deep charcoal background with subtle gradient
- 3D viewport as centerpiece
- Gold accent on "Continue to Payment" button
- Smooth animations on component selection

### Order Summary
- Alt surface cards for each section
- Serif typography for headers
- Gold callout for total price
- Hover states on edit links

### Admin Dashboard
- Consistent color palette across panels
- Gold status indicators
- Smooth state transitions
- High-contrast table layouts

## Theming

Both light and dark modes use the same gold accent color as the primary highlight, ensuring brand consistency across contexts.

The system intentionally uses a dark-first approach because:
1. Premium aesthetic (luxury brand positioning)
2. Better for 3D visualization (dark backgrounds make CGI pop)
3. Reduced eye strain for long configuration sessions
4. Professional tone for admin dashboard
