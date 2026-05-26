---
name: Zenith AI
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#44474c'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#75777d'
  outline-variant: '#c5c6cc'
  surface-tint: '#555f70'
  primary: '#212b3a'
  on-primary: '#ffffff'
  primary-container: '#374151'
  on-primary-container: '#a3adc0'
  inverse-primary: '#bdc7db'
  secondary: '#585f6c'
  on-secondary: '#ffffff'
  secondary-container: '#dce2f3'
  on-secondary-container: '#5e6572'
  tertiary: '#362811'
  on-tertiary: '#ffffff'
  tertiary-container: '#4e3e25'
  on-tertiary-container: '#c0a989'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e3f7'
  primary-fixed-dim: '#bdc7db'
  on-primary-fixed: '#121c2a'
  on-primary-fixed-variant: '#3d4757'
  secondary-fixed: '#dce2f3'
  secondary-fixed-dim: '#c0c7d6'
  on-secondary-fixed: '#151c27'
  on-secondary-fixed-variant: '#404754'
  tertiary-fixed: '#f8dfbc'
  tertiary-fixed-dim: '#dbc3a2'
  on-tertiary-fixed: '#261905'
  on-tertiary-fixed-variant: '#55442b'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Noto Sans SC
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 26px
  body-lg:
    fontFamily: Noto Sans SC
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Noto Sans SC
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
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
  element-gap: 16px
  stack-tight: 4px
---

## Brand & Style

The design system is centered on the concept of "Invisible Intelligence." It targets high-productivity professionals requiring a calm, focused environment for real-time voice interaction and task management. 

The aesthetic is **High-End Minimalism**. It prioritizes extreme clarity, reduction of cognitive load, and a sense of "breathable" space. By utilizing a monochromatic foundation with high-quality typography and precise geometry, the interface feels less like a tool and more like a sophisticated digital companion. The emotional response is one of reliability, serenity, and effortless efficiency (冷静, 智能, 高效).

## Colors

The palette is intentionally restrained to maintain a professional and "airy" atmosphere. 

- **Primary (#374151):** A deep slate/charcoal used for high-emphasis text, active states, and primary iconography. It provides a softer contrast than pure black.
- **Secondary (#6B7280):** A muted gray for supporting text and non-critical UI elements.
- **Neutral / Surface (#F9FAFB, #F3F4F6):** Used for background layering and subtle structural containers to differentiate content without using heavy borders.
- **Background (#FFFFFF):** The dominant color, providing the "spacious" feel and maximizing legibility.

## Typography

Typography is the primary driver of the hierarchy. For desktop, we utilize **Hanken Grotesk** for Latin characters and headings to provide a modern, precise feel. For Chinese characters and body text, **Noto Sans SC** (or system equivalents like PingFang SC) is used to ensure perfect legibility and weight balance.

- **Titles (标题):** Use Medium weights with tight letter-spacing for a "designed" look.
- **Body (正文):** Use Regular weight with generous line height (1.5x+) to ensure readability during long interactions.
- **Labels (标签):** Use uppercase for English or slightly bolded Chinese characters to denote utility functions.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model optimized for PC desktops. Central content areas (like the AI conversation thread) are centered with maximum widths, while utility sidebars are fixed.

- **Grid:** A 12-column grid is used for complex dashboards, but the primary interface relies on a "Single Column Focus" to minimize distraction.
- **Margins:** High margins (32px+) are used at the edges of the window to create the "spacious" brand feel.
- **Density:** Low density is preferred. Every element must have "room to breathe."

## Elevation & Depth

This design system avoids heavy drop shadows. Instead, it uses **Tonal Layering** and **Soft Ambient Occlusion**.

- **Level 0 (Base):** #FFFFFF background.
- **Level 1 (Cards/Sidebar):** #F9FAFB surface with a 1px #E5E7EB border.
- **Level 2 (Floating/Modals):** A very soft, diffused shadow: `0px 10px 30px rgba(0, 0, 0, 0.04)`.
- **Interaction:** On hover, elements should subtly shift in background color rather than increasing shadow depth, maintaining a flat, sophisticated profile.

## Shapes

The shape language is "Soft-Modern." We use a medium corner radius (0.5rem / 8px) for standard components like input fields and cards. 

- **Interactive Elements:** Buttons and tags use a slightly higher radius to feel more approachable.
- **Visual Rhythm:** Consistency in corner radii across different sizes is vital; buttons, containers, and image masks should all share the same 8px base to create a unified visual language.

## Components

### Buttons (按钮)
- **Primary:** Background #374151, Text #FFFFFF. No border.
- **Secondary:** Background #FFFFFF, Border 1px #E5E7EB, Text #374151.
- **Style:** 8px rounded corners, 12px 24px padding.

### Voice Waveform (语音波形)
- A signature component for the AI agent. Use a series of thin vertical lines with varying heights.
- **Color:** Soft primary gray (#374151).
- **Animation:** Fluid, organic movement rather than mechanical.

### Input Fields (输入框)
- Minimalist line or subtle fill (#F9FAFB).
- **Focus State:** 1px border #374151. No glow.
- **Placeholder:** #9CA3AF.

### Cards (卡片)
- Used for task items or information blocks.
- White background, 1px light gray border, 8px radius.
- Padding should be generous (20px - 24px).

### Icons (图标)
- Use thin-stroke (1.5px or 1px) outlined icons. 
- Avoid filled icons unless it represents an active "on" state.
- Size standard: 20px or 24px within a 32px or 40px hit area.

### Status Indicators (状态提示)
- Small, solid dots for "AI Listening" (在线) or "Processing" (处理中) using the primary accent color.