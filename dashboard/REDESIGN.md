# Dashboard Redesign Plan

> **Status: COMPLETE (2026-03-31).** The redesign described below has been implemented. The dashboard now features an Apple keynote-style hero screen with glassmorphic ALICE text, zoom-through animation, and a consumer-facing 3-column layout with inline panels for personality, living behaviors, object memory, LLM modifiers, and system status. 12 legacy components deleted, replaced with clean inline implementations.

## Vision

Glassmorphism UI: dark, translucent panels, frosted glass depth. The glass brain sits in the center. Around it: object memory, spatial preferences, routine history. Personality indicators pulse subtly.

This isn't a debug tool. This is the **product interface**.

## New Components

### SpatialMapPanel
- 3D visualization of the desk using Three.js
- Point cloud rendered from SpatialMap data
- Objects labeled and positioned in 3D space
- Real-time updates as ALICE moves
- Replaces the 2D minimap

### ObjectMemoryPanel
- Shows what ALICE remembers across sessions
- Object list with icons, last-seen time, preference strength
- "New" and "Moved" badges for changes since last session
- Color-coded by ObjectCategory (drinkware, electronics, etc.)

### PersonalityPanel
- Emotional state indicator (content, curious, annoyed, focused, reluctant, satisfied)
- Overall mood bar (0.0 → 1.0)
- Override streak counter
- Voice gate status (open/closed)
- Speed multiplier visualization

### DeskPresetSelector
- Grid of preset cards (Studying, Drawing, Working, Clean)
- Active preset highlighted
- Audience vote counts per preset
- Used in Performance mode Act 5

### PerformanceTimeline
- Horizontal timeline showing the 6-act arc
- Current act highlighted with progress indicator
- Act labels match REMODEL spec

### OrganizationProgress
- Move list with checkmarks
- Current move highlighted
- Object being moved with from/to positions

## Layout

```
┌────────────────────────────────────────────────────────────┐
│  Header: ALICE status | Mode | Personality mood bar        │
├────────────┬───────────────────────────┬───────────────────┤
│            │                           │                   │
│  Camera    │     Glass Brain /         │  Object Memory    │
│  Feed      │     Spatial Map           │  Panel            │
│            │     (center, large)       │                   │
│            │                           │                   │
├────────────┼───────────────────────────┤                   │
│ Personality│  Desk Preset Selector     │                   │
│ Panel      │  / Organization Progress  │                   │
├────────────┴───────────────────────────┴───────────────────┤
│  Performance Timeline (full width, only in performance)    │
└────────────────────────────────────────────────────────────┘
```

## Design Tokens

- Background: `#0a0a0f`
- Panel: `rgba(255, 255, 255, 0.05)` with `backdrop-filter: blur(20px)`
- Border: `rgba(255, 255, 255, 0.08)`
- Accent: `#7c5cff` (personality/active)
- Text primary: `rgba(255, 255, 255, 0.9)`
- Text secondary: `rgba(255, 255, 255, 0.5)`
- Category colors: match `_category_color()` from yolo_detector.py

## Data Sources

All panels consume WebSocket messages from the tensor server:
- `state_sync` — full ALICE state (personality, mode, arm, etc.)
- `camera_frame` — base64 encoded JPEG
- `activations` — binary CNN activation data for glass brain
- New message types needed:
  - `spatial_map` — point cloud data (Nx6 float32 array)
  - `object_memory` — JSON snapshot of object records
  - `org_status` — desk organizer state + move list
  - `presence` — face count, distance, looking-at-desk
  - `performance_act` — current act number + label

## Implementation Order

1. Design tokens + global glassmorphism styles
2. PersonalityPanel (reads existing state_sync)
3. ObjectMemoryPanel (new WebSocket message)
4. DeskPresetSelector (new WebSocket message)
5. SpatialMapPanel (Three.js point cloud renderer)
6. PerformanceTimeline (reads demo_act from state_sync)
7. OrganizationProgress (new WebSocket message)
8. Layout refactor — swap existing panels for new ones
