# FieldOps Modern SaaS UI / UX Architecture

## 1. Executive Summary & Design Philosophy

FieldOps is an enterprise field operations platform and AI-native service delivery system. The user experience is engineered to be **modern, professional, transparent, and high-velocity**, rejecting generic CRUD admin templates, raw chatbot clones, and toy landing pages.

### Design Principles:
1. **Persona-Specific Information Density**:
   - **Customer Portal**: Consumer-grade simplicity, welcoming, calm status projections, mobile-optimized, focused on single primary tasks.
   - **Operator Dashboard**: High-density, high-velocity operational cockpit, desktop-optimized, fast keyboard shortcuts, batch actions, and sub-second context switching.
   - **Admin Console**: Governance-first, platform health matrix, policy configuration, audit trails, and security telemetry.
2. **AI-Native Grounding (Zero-Hallucination UX)**:
   - AI summaries, context panels, and dispatch suggestions are synthesized deterministically from structured backend data.
   - AI panels explain *why* and provide situational context, but **never execute irreversible mutations directly**; operational control remains strictly within explicit Human-in-the-Loop (HITL) workflows.
3. **Progressive Disclosure**:
   - Primary queues emphasize critical triaging metrics (SLA health, urgency, required actions).
   - Secondary operational details (audit logs, full candidate breakdowns, timeline events) are revealed on demand via slide-over Drawers and Collapsible Cards.
4. **Accessible Semantics**:
   - Status indicators pair standardized hex colors with distinct geometric/semantic icons and text labels (WCAG AA compliant, colorblind-safe).
   - Focus rings, keyboard shortcuts (`Ctrl+K` / `Cmd+K`, `ESC`), and ARIA modal traps replace native browser dialogs (`window.confirm`).

---

## 2. Design Tokens & Styling Architecture

The design token system is built on Tailwind CSS v3 with centralized styling tokens defined in `frontend/tailwind.config.js` and normalized in `frontend/src/index.css`.

### 2.1 Color Palette & Token Hierarchy

| Token Group | Values / Hues | Purpose |
| :--- | :--- | :--- |
| **Brand / Primary** | `indigo-50` to `indigo-950` (`primary: #4f46e5`, `hover: #4338ca`) | Primary navigation, active selections, CTA highlights |
| **Neutral / Slate** | `slate-50` to `slate-950` | Structural borders (`slate-200`), muted text (`slate-500`), body copy (`slate-800`), headings (`slate-900`) |
| **Success** | `emerald-50` to `emerald-700` (`#059669`) | Resolved SLAs, scheduled appointments, verified integrations |
| **Warning** | `amber-50` to `amber-700` (`#d97706`) | SLA at-risk warnings, required information supplements |
| **Critical / Danger**| `rose-50` to `rose-700` (`#e11d48`) | SLA breaches, escalated tickets, cancellation actions, system errors |
| **Info / Tech** | `sky-50` to `sky-700` / `purple-50` to `purple-700` | Dispatch algorithmic scoring, timeline event feeds |

### 2.2 Elevation & Shadows
- `shadow-card`: `0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.04)` (subtle modern border-elevation)
- `shadow-elevated`: `0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.03)` (hover states and bento items)
- `shadow-popover`: `0 10px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.05)` (modals, drawers, command palette)

### 2.3 Typography & Focus
- **Font Stack**: `Inter`, system-ui, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`, `sans-serif`.
- **Tabular & Monospace**: `ui-monospace`, `SFMono-Regular`, `Menlo`, `Monaco`, `Consolas`, `monospace` for Ticket IDs, timestamps, and coordinates.
- **Focus Rings**: Standardized `.focus-ring` utility (`focus-visible:ring-2 focus-visible:ring-indigo-500/30 focus-visible:outline-none focus:border-indigo-500`).

---

## 3. Shared UI Component Library (`frontend/src/components/ui/`)

| Component | Role & Architecture |
| :--- | :--- |
| `Button` | Standardized button with 5 variants (`primary`, `secondary`, `outline`, `ghost`, `danger`), 3 sizes (`sm`, `md`, `lg`), built-in loading spinner, and icon slots. |
| `Card`, `StatCard` | Card structural primitives (`CardHeader`, `CardTitle`, `CardContent`, `CardFooter`) and metric stat cards with trend indicators and status coloring. |
| `Badge` | Compact pill badge with dot indicator for low-emphasis categorical tags. |
| `StatusBadge` | Semantic status indicator for SLAs, urgency, workflows, appointments, roles, and outbox states with mandatory semantic icons (colorblind accessible). |
| `Input`, `Textarea`, `Select` | Accessible form controls featuring label binding, validation error text, helper hints, and standardized focus rings. |
| `Skeleton` | Shimmer skeletons for zero-layout-shift loading: `CardSkeleton`, `TableSkeleton`, and `DetailSkeleton`. |
| `Dialog` | Accessible modal dialog with backdrop blur, keyboard ESC listener, body scroll locking, and accessible focus trapping (fully replacing `window.confirm`). |
| `Drawer` | Slide-over lateral panel for desktop fast previewing without tearing down user list context. |
| `CommandPalette` | Global `Ctrl+K` / `Cmd+K` keyboard navigator providing instant search across routes, common actions, and system views. |
| `DataTable` | High-density data grid with sticky table headers, hover interactions, empty states, and row selection handlers. |
| `EmptyState` / `ErrorState` | Uniform zero-data and API failure recovery views featuring descriptive illustrations, messaging, and explicit retry callbacks. |
| `PageHeader` | Standardized header container with breadcrumb/back links, title, subtext, and right-aligned action buttons. |
| `Toast` / `ToastContext` | Context-driven ephemeral notification system with auto-dismissal (3.5s), swipe dismissal, and color-coded status banners. |

---

## 4. Role-Specific Information Architecture

```
                                  [ FieldOps System ]
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
   Customer Portal                 Operator Dashboard                  Admin Console
(Self-service / AI Chat)        (Triaging & Dispatch Cockpit)       (Governance & Health)
   • Conversational Intake         • Bento Overview & Metrics          • Health Matrix
   • Live Structured Draft         • Action-Required Queue             • Workforce Capacity
   • Calm Status Projection        • Hero Dispatch Explainability      • Policy Version Control
   • Single-click Reschedule       • Quick Preview Drawers             • Real-time Audit Stream
   • Self-Service Cancel           • Sticky Action Bar (HITL)          • Integration Diagnostics
```

### 4.1 Operator Dashboard
- **Bento Grid Overview**:
  - `HeroCard`: Action-Required Queue highlights highest-urgency unassigned or at-risk tickets.
  - `StatCard`: SLA compliance rate (computed deterministically), today's scheduled visits, waiting approvals.
  - `AI Operations Summary`: Synthesized bulleted operational posture based on live backend aggregations.
- **Dispatch Recommendation Hero Card**:
  - Highlights the top-ranked technician candidate.
  - Visualizes composite score breakdown with horizontal progress bars (Distance / Proximity, Skill Match, Workload Balance).
  - Explicit "Why this technician?" rationales extracted directly from the scoring engine.
  - Alternative candidate collapsible list for operator discretion and override.
- **Quick Preview Drawer**:
  - Clicking any table row in the Service Requests or Appointments queue opens a 480px slide-over preview.
  - Allows the operator to inspect customer details, SLA clock, and assigned specialist without losing page position or query filters.
- **Sticky Action Bar**:
  - Fixed to the bottom of the viewport on long Request Detail pages.
  - Keeps high-frequency operations (`Assign Candidate`, `Escalate Ticket`, `Reschedule Visit`) within thumb/mouse reach regardless of scroll depth.

### 4.2 Customer Portal
- **Friendly & Trust-Inducing Greeting**:
  - Simple, non-marketing greeting: *"How can we help today, {Name}?"*
  - Instant visibility into active ticket status and next scheduled visit date.
- **Calm Status Projections**:
  - Translates complex internal state machines (`ready_for_review`, `waiting_for_approval`, `dispatched`) into reassuring human milestones:
    - *"Request Received: Our dispatch team is reviewing your requirements."*
    - *"Finding Best Technician: Matching qualified technicians in your district."*
    - *"Visit Confirmed: A certified technician has been reserved."*
- **Conversational Service Intake**:
  - 2-column layout on desktop: Live conversation history on left; real-time structured ticket draft on right.
  - Responsive mobile experience: Persistent bottom drawer / slide-up draft sheet.
  - 3-step intake progression indicator: `1. Intake` &rarr; `2. Matching` &rarr; `3. Confirmation`.
  - Resilient retry UI on network timeout with conversation state persistence.

### 4.3 Admin Console
- **Platform Health & Outbox Diagnostic**:
  - Bento card monitoring PostgreSQL connectivity, Redis broker latency, and transactional outbox queue depth.
- **Workforce Capacity & Skills Distribution**:
  - Real-time technician availability, active assignments, and coverage by specialty.
- **Policy Version Governance**:
  - Active SLA thresholds, escalation tiers, and auto-dispatch rules with audit trail timestamps.
- **Recent Audit Stream**:
  - Chronological activity log showing actor identity, action type, target entity, and timestamp.

---

## 5. Modern Web & Accessibility Engineering

1. **Non-Color-Only Status Communication (WCAG AA 1.4.1)**:
   Every status tag combines color tokens with semantic Lucide SVG icons (e.g., `AlertTriangle` for Breached, `Clock` for At Risk, `CheckCircle2` for Scheduled, `XCircle` for Cancelled).
2. **Keyboard Navigation & ARIA**:
   - `Ctrl+K` / `Cmd+K` global command search with auto-focus and keyboard arrow navigation.
   - Escape key dismisses modals and drawers.
   - Accessible focus-trap prevents focus escaping active dialogs.
3. **Responsive Resilience**:
   - Operator and Admin views degrade gracefully from multi-column bento grids (desktop) to stacked linear layouts (tablet).
   - Customer Portal is fully mobile-first, ensuring customers can request help or reschedule appointments seamlessly on phone screens.
4. **Resilient Data Fetching & Caching**:
   - TanStack Query handles background invalidation, optimistic updates, and automatic retry.
   - Shimmer skeletons eliminate cumulative layout shift (CLS) during cache hydration.
