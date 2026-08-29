# Persistent-world UI/UX

Active surface: `PremiumPersistentWorldSurface.tsx`, hosted by `PersistentWorldShell.tsx`. The world is immutable; selection changes camera, detail, emphasis, and inspector context only.

Controls: click selects; double-click parent moves up; double-click empty space resets; wheel zooms around the cursor (0.55–3.25); middle-drag pans; Alt+Left moves up; Reset clears focus; Full-world uses density LOD; Trace highlights an existing path; Full screen uses the browser API with CSS fallback. A structured exact-ten list provides keyboard/touch access.

Renderer language: deterministic cubic tethers, sector hues, bounded child hue variation, semantic glyphs, particles, parallax, orbital guides, glints, and 820–1,220 ms cinematic camera transitions. Reduced motion jumps the camera and disables continuous effects while preserving meaning.

Inspector and hover keep identity, value, purpose, evidence, and source status separate. The accepted node-title correction is locked: graph titles are identity-only; compact values appear only in hover/inspector data fields. Human acceptance: commit `bc6c8f87a592378c95d1ffe773c44fdbe641ae55` is PASS for that defect only.

Known risks: full-world traverses 1,111 placements and 3,110 fixture relationships; continuous animation recomputes paths/styles; no spatial index; long transitions may feel laggy; Canvas accessibility depends on the structured list. Preserve strict LOD. Never make all 1,111 nodes simultaneously semantic and interactive.
