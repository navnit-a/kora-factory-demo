# Design direction: PlatformCon Day Planner

This is the look the app follows. Adapt it to each screen rather than copying a layout; keep new work
consistent with what is already shipped; where this file says nothing, make a good decision and keep it
consistent from then on.

The feel is calm, spacious and friendly: lots of whitespace, soft light surfaces, rounded shapes, one
confident accent used sparingly, and type that does the work instead of decoration. Think of a
well-run conference app you can read at a glance in a busy foyer.

## Colour: "Harbour"

A Sydney harbour palette: sandstone paper, deep harbour water, a ferry-teal accent and a late-sun
highlight for whatever is happening now. Define these as CSS variables and use only the variables.

| Token | Value | Use |
|---|---|---|
| `--paper` | `#F6F4EF` | Page background |
| `--surface` | `#FFFFFF` | Cards, dialogs, inputs |
| `--surface-muted` | `#EFECE5` | Grouped rows inside a card, quiet sections |
| `--hairline` | `rgba(16, 32, 31, 0.08)` | 1px borders on cards and inputs |
| `--ink` | `#10201F` | Headings, primary buttons |
| `--text` | `#1E2A2A` | Body text |
| `--text-muted` | `rgba(30, 42, 42, 0.62)` | Secondary text, captions, metadata |
| `--accent` | `#0F766E` | Links, selected states, toggles, focus ring |
| `--accent-strong` | `#0B5B55` | Accent hover and pressed |
| `--accent-soft` | `#DDEFEC` | Badge and chip backgrounds, selected rows |
| `--now` | `#F4A340` | The "happening now" marker and progress, never body text |
| `--danger` | `#B42318` | Errors only |

Dark mode inverts the surfaces: `--paper #0E1A19`, `--surface #152423`, `--surface-muted #1C2E2D`,
`--text #E8EEEC`, `--text-muted rgba(232, 238, 236, 0.64)`, accent `#3FB8AC`. The `--now` colour stays.

Contrast: body text on paper and surface is above 12:1; `--accent` on white is above 5:1; white on
`--accent` and on `--ink` passes AA. Keep it that way when adding colours.

## Type

Poppins, from Google Fonts, weights 400 and 500 only. Sizes in px, line heights as ratios.

| Role | Size / line height | Weight | Tracking |
|---|---|---|---|
| Page title | 32 / 1.25 | 500 | -0.5 |
| Section heading | 24 / 1.3 | 500 | -0.25 |
| Card title | 16 / 1.6 | 500 | 0 |
| Body | 14 / 1.6 | 400 | 0 |
| Caption and metadata | 14 / 1.5 | 400, `--text-muted` | 0 |
| Button | 14 / 1.5 | 500 | 0.1 |

Times use tabular figures (`font-variant-numeric: tabular-nums`) so a schedule column lines up.

## Space and shape

- Spacing steps: 4, 8, 12, 16, 24, 32, 48. Containers pad 32 on desktop and 16 on a phone; items
  inside a card sit 8 or 12 apart; sections sit 24 to 48 apart.
- Radius: 8 for inputs and small controls, 16 for cards and grouped rows, 24 for dialogs and sheets,
  fully round for buttons, chips and badges.
- Cards are `--surface` with a 1px `--hairline` border and no shadow. Dialogs float on a soft shadow
  (`0 24px 48px rgba(16, 32, 31, 0.16)`) over a dimmed backdrop.
- Breakpoints: phone 393, tablet 1024, desktop 1440. Design phone first; attendees use phones.

## Components

- **Buttons are pills.** Primary: `--ink` fill, white text. Secondary: `--surface` with a 1px
  hairline border and `--ink` text. Text buttons for low emphasis. Minimum height 44.
- **Session card:** time on the left in tabular figures, title and room on the right, track as a small
  `--accent-soft` chip. The current session gets a 4px `--now` bar on its leading edge and a "Now"
  label, not a different background.
- **Step and count badges:** 22px circles, `--accent-soft` fill, `--accent` digits.
- **Switches** for on/off settings ("Show only my agenda"), `--accent` when on.
- **Grouped rows:** a card holding stacked `--surface-muted` rows with 16px radius and 8px gaps, each
  row a label on the left and its control on the right.
- **Empty states:** one short sentence saying what will appear here, and the one action that fills it.

## Motion

Short and purposeful: 150 to 200 ms ease-out for hover, press and toggle; one staggered fade-up when
the schedule first loads; the `--now` bar pulses gently once when a session starts. Respect
`prefers-reduced-motion` by turning all of it off.

## Accessibility floor

Real buttons and links, labels on every input, a visible 2px `--accent` focus ring, 44 by 44 minimum
touch targets, `aria-hidden` on decorative icons, `aria-label` on icon-only buttons, and nothing that
relies on colour alone, which is why "Now" is also written as text.

## What not to do

No default system or overused fonts, no purple or magenta, no gradients on text, no drop shadows on
cards, no emoji as icons, no stock illustration. Where the design is silent, prefer whitespace over
decoration.
