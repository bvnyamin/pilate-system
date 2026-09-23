---
name: Aldra Administrative Interface
colors:
  surface: '#1a1110'
  surface-dim: '#1a1110'
  surface-bright: '#423635'
  surface-container-lowest: '#150c0b'
  surface-container-low: '#231918'
  surface-container: '#271d1c'
  surface-container-high: '#322726'
  surface-container-highest: '#3e3230'
  on-surface: '#f1dedb'
  on-surface-variant: '#dcc0bc'
  inverse-surface: '#f1dedb'
  inverse-on-surface: '#392e2c'
  outline: '#a48b87'
  outline-variant: '#56423f'
  surface-tint: '#ffb4a9'
  primary: '#ffb4a9'
  on-primary: '#61120c'
  primary-container: '#ff8a7a'
  on-primary-container: '#762219'
  inverse-primary: '#9f4035'
  secondary: '#e1c299'
  on-secondary: '#402d10'
  secondary-container: '#5b4526'
  on-secondary-container: '#d2b48c'
  tertiary: '#58dcb6'
  on-tertiary: '#00382a'
  tertiary-container: '#34c09b'
  on-tertiary-container: '#004938'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdad5'
  primary-fixed-dim: '#ffb4a9'
  on-primary-fixed: '#410000'
  on-primary-fixed-variant: '#7f2920'
  secondary-fixed: '#feddb3'
  secondary-fixed-dim: '#e1c299'
  on-secondary-fixed: '#281801'
  on-secondary-fixed-variant: '#584324'
  tertiary-fixed: '#77f9d1'
  tertiary-fixed-dim: '#58dcb5'
  on-tertiary-fixed: '#002118'
  on-tertiary-fixed-variant: '#00513f'
  background: '#1a1110'
  on-background: '#f1dedb'
  surface-variant: '#3e3230'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '500'
    lineHeight: '1.3'
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 28px
    fontWeight: '500'
    lineHeight: '1.3'
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-padding: 32px
  gutter: 24px
  sidebar-width: 260px
  sidebar-collapsed: 80px
---

## Brand & Style

The design system is centered on a premium, minimalist aesthetic tailored for boutique wellness environments. It moves away from cold, corporate layouts toward an atmosphere of "Quiet Luxury"—focused on high-end service, calm organization, and physical grace.

The visual direction combines **Minimalism** with subtle **Glassmorphism**. It utilizes a deep, dark-mode foundation to reduce eye strain for administrators while allowing high-energy accents to guide the user's attention. The interface should feel like a high-end concierge tool: discreet, sophisticated, and effortless.

## Colors

This design system uses a sophisticated dark palette to evoke a premium studio environment. 

- **Primary (Soft Coral):** Reserved for high-priority actions, primary buttons, and active states. It represents the energy and vitality of the Pilates practice.
- **Secondary (Sand):** Used for subtle accents, secondary iconography, or decorative borders to ground the vibrant coral with an earthy, organic tone.
- **Neutral Stack:** The background uses a rich anthracite (#121212) to provide depth, while secondary surfaces (#1E1E1E) define cards and navigation containers.
- **Typography:** Warm white (#F5F5F5) is used for all body text to ensure high legibility against the dark background without the harshness of pure white.

## Typography

The typography strategy employs a pairing of **Playfair Display** for high-level headings and **Inter** for functional UI elements. 

- Use **Playfair Display** sparingly for page titles and large statistics to inject an editorial, boutique feel.
- Use **Inter** for all administrative data, tables, and forms. Its neutral, systematic nature ensures clarity in high-density information environments.
- Maintain generous line-heights (1.5+) for body copy to preserve the sense of "breathing room" and wellness.

## Layout & Spacing

The layout follows a **Fluid Grid** model with strict maximum widths for content readability. 

- **Sidebar Navigation:** A fixed-position sidebar on the left, collapsible to an icon-only view. The sidebar background should be slightly lighter than the main background (#1E1E1E) to define the application's structure.
- **Margins & Gutters:** A standard 24px gutter is used between cards. Global page margins are set to 32px to provide the requested "breathing room."
- **Desktop (1440px+):** 12-column grid.
- **Tablet (768px - 1024px):** 8-column grid; sidebar becomes a floating overlay or stays fixed if space permits.
- **Mobile (<768px):** 4-column grid; sidebar moves to a bottom navigation bar or a hamburger menu.

## Elevation & Depth

Depth is achieved through **Tonal Layers** and **Subtle Shadows** rather than heavy gradients.

- **Level 0 (Base):** #121212 (Main background).
- **Level 1 (Cards/Sidebar):** #1E1E1E. These surfaces should feature a 1px border of #2A2A2A to provide crisp definition.
- **Shadows:** Use a single, highly diffused shadow style for cards: `0px 10px 30px rgba(0, 0, 0, 0.5)`. This creates a floating effect that feels modern and premium.
- **Active States:** Elements being interacted with should use a soft outer glow in the Primary color (#FF8A7A) at 20% opacity.

## Shapes

The design uses **Rounded** geometry (8px to 16px) to soften the dark aesthetic and align with the "wellness" theme.

- **Cards & Large Containers:** Use 16px (`rounded-xl`) corner radius.
- **Buttons & Inputs:** Use 8px (`rounded-md`) corner radius for a balance of modernism and approachable design.
- **Badges/Status Tags:** Use a full pill-shape (999px) to distinguish them from functional buttons.

## Components

### Buttons
- **Primary:** Background #FF8A7A, Text #121212 (for contrast). No border.
- **Secondary:** Transparent background, 1px border in #D2B48C, Text #D2B48C.
- **Ghost:** Transparent background, Text #F5F5F5.

### Status Badges
Badges use low-opacity backgrounds with high-opacity text for an elegant, non-obtrusive look.
- **Paid / Active:** Background: rgba(46, 204, 113, 0.1), Text: #2ECC71.
- **Pending:** Background: rgba(210, 180, 140, 0.1), Text: #D2B48C.
- **Inactive / Overdue:** Background: rgba(231, 76, 60, 0.1), Text: #E74C3C.

### Progress Bars
Track background should be #2A2A2A. The indicator should be a gradient from #FF8A7A to #D2B48C for a premium "wellness" feel. Height should be slim (6px).

### Tables & Forms
- **Tables:** No vertical borders. Use horizontal dividers in #2A2A2A. Header text should use `label-md` (uppercase) for clear hierarchy.
- **Inputs:** Background #1E1E1E, Border 1px #333333. On focus, the border changes to #FF8A7A.

### Navigation Sidebar
Collapsible design with active states indicated by a 4px vertical "coral" bar on the left edge of the menu item and a subtle background shift to #2A2A2A.