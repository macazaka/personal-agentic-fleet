---
description: Enforce strict laptop CPU and RAM resource constraints across all Personal Agentic Fleet enhancements
---

# Laptop Hardware & Resource Constraints (Mandatory Engineering Rule)

Always design and implement every Personal Agentic Fleet enhancement within strict laptop CPU and RAM limits:

1. **Zero-Polling & Event-Driven UI**:
   - Prefer pure CSS rules (e.g., `body.afcc-alt-xray-active [data-shortcut]::after`), single delegated event listeners, and lazy DOM hydration over `setInterval` or continuous `requestAnimationFrame` loops.
2. **Idle & Hidden-Tab Suspension (`0.0%` Idle CPU)**:
   - Any periodic poll or WebAudio `AudioContext` MUST check `document.hidden` and auto-suspend (`audioCtx.suspend()`, `clearInterval`) when idle or when its panel/dock is closed.
3. **Silence & Unchanged-State Short-Circuiting**:
   - Audio DSP, canvas visualizers, and telemetry polls MUST short-circuit on silence (`rms < 0.013`) or unchanged `latest_step` before running FFTs, autocorrelation, or DOM/canvas repaints, and deduplicate DOM text mutations.
4. **Zero-GC Hot Loops & Bounded Ring Buffers**:
   - Reuse pre-allocated typed arrays (e.g., `_SHARED_NSDF_BUF`) instead of allocating objects inside timer callbacks, and enforce strict ring-buffer caps on all in-memory history arrays (`MAX_UTTERANCE_FRAMES = 80`, chat turns `<= 40`).
