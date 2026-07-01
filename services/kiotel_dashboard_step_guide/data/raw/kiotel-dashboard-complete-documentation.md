# Kiotel Dashboard — Agent Documentation

This file contains the Kiotel **Agent Dashboard** (front-desk operator) help documentation.
It is written in plain language for non-technical users and a help chatbot, and it
documents every agent-facing page, every button (with its on-screen location), what each
control does, when to use it, and how to recover from failure states.

Admin Console configuration screens are not covered here — this document focuses only on
what a front-desk **agent** sees and uses. Where agent behavior depends on something an
admin configures elsewhere (e.g. transaction timeout length, device assignment, feature
permissions), that dependency is mentioned briefly without documenting the admin UI itself.

It is organized into five parts. Start with **Part 1 (Overview & Core Concepts)** — it
explains the ideas every other part depends on (online/offline devices, the
control/observer model, and the transaction-session gate).

**Key mental model:** A front-desk agent signs in, selects one kiosk (device) to operate,
and works it remotely. A kiosk can be operated by only one agent at a time; everyone else
is an observer whose action buttons are blocked until they take or request control. Many
guest-facing actions (scan, cash, key, print, ratings, photo, guest details, document
signature) only work during an active transaction session. When an agent presses a button,
the kiosk performs the action on its hardware and reports status back — so actions only
work when the device is online and the agent has control. When something does not work, the
usual causes (in order) are: device offline, you are an observer (no control), no active
transaction, or the page needs a refresh to re-sync.

**Conventions:** on-screen labels and status words appear in "double quotes"; "Route/URL"
lines give the page's address-bar path (useful for identifying a page); location notes
("top-right header", "card footer", and so on) tell you where on the screen to look.

## Contents

- [Part 1 — Overview & Core Concepts](#part1)
- [Part 2 — Agent Dashboard (Front-Desk Operator)](#part2)
- [Part 3 — Kiosk Features & Hardware Behavior](#part3)
- [Part 4 — Troubleshooting & Recovery](#part4)
- [Part 5 — Hardware Guide & Device Configuration](#part5)

---

<a id="part1"></a>

## Part 1 — Overview & Core Concepts

> This document explains the cross-cutting ideas that apply to *every* page of the
> Kiotel agent dashboard. The chatbot should read this first, because almost every
> page-specific question (cash dispenser, scanner, key dispenser, etc.) depends on
> the ideas below: **who is logged in**, **which device is selected**, **whether the
> device is online**, **who has control of the device**, and **whether a transaction
> session is active**.

---

### 1. The Agent Dashboard

The Kiotel Agent Dashboard lives at /dashboard. Front-desk **agents** sign in at /login to
remotely operate one hotel kiosk at a time: greet the guest over video, scan IDs, take
cash, dispense room keys, print receipts, and more. An agent operates **one device at a
time**.

(A separate Admin Console exists for fleet-wide configuration, but its screens are outside
the scope of this document.)

---

### 2. The hardware behind the dashboard

Every "device" in the dashboard is a physical **kiosk** that sits in a hotel lobby. Each
kiosk has a touch screen, a camera, a **cash dispenser/recycler**, a **key/card
dispenser**, an **ID/passport scanner**, **indicator lights**, a **receipt printer**, a
speaker for spoken messages, and a **Google Meet** video window for talking to the guest.

When an agent presses a button in the dashboard, the kiosk performs that action on its
physical hardware and reports the result back. See the kiosk-features section for what
each feature does on the hardware.

---

### 3. How an action reaches the kiosk

When an agent presses a button, the action is sent over a live connection to the selected
kiosk. The kiosk carries it out and sends the result back, which is what the agent sees on
screen. Two simple rules govern whether an action works:

1. **The device must be online** (connected). If it's offline, nothing the agent sends
   will arrive.
2. **The agent must have control** of the device. If another agent is operating it, the
   first agent is an "observer" and their buttons are blocked.

**Practical implication for users:** if a button "does nothing", the two most common
causes are (1) the device is **offline**, or (2) the agent **doesn't have control** of
the device (they're an observer).

---

### 4. Agent login & device selection (two-step sign-in)

Agents sign in in **two steps**:

1. **Sign in** (/login) — the agent enters their **Agent ID** and **password**. On
   success they're taken to the device-selection screen.
2. **Pick a device** (/select-device) — the agent chooses **which kiosk** they want to
   operate (a search box plus cards showing each device's online/offline status, with a
   shortcut to their last-used device). Choosing a device opens the main dashboard.

Notes:
- An agent can only pick devices they are **assigned** to, and that assignment is checked
  every time — if the assignment is removed, the agent loses access.
- A record of the agent's browser/computer is taken at sign-in (used for the
  trusted-browser / login-approval checks).
- **Switching device:** there is a **"Switch Device"** button in the agent top bar. It
  drops the current device and returns the agent to the device-selection screen.
- **Logout** signs the agent out and returns to the sign-in screen.

---

### 5. Device online/offline & connection status

- "**Online**" means the kiosk is currently connected.
- The dashboard keeps each device's online/offline status up to date automatically — it
  refreshes on a short timer and updates immediately whenever any kiosk connects or
  disconnects.
- The agent top bar and device pages show a **connection indicator** ("Online" /
  "Offline", green/red). If it shows **Offline**, actions will not reach the kiosk.
- The dashboard's own connection can also drop briefly (a network blip). When that
  happens it reconnects on its own and re-checks which devices are online.

**Troubleshooting:** if status looks stuck, **refresh the page** — this rebuilds the
connection and re-syncs device status and control. This is the single most common
recovery action across the whole dashboard.

---

### 6. Device control & the "observer" model (very important)

A kiosk can be **operated by only one agent at a time**. Every other agent viewing that
device is an **observer** (read-only — they see status but their action buttons are
blocked).

The control state of the selected device is one of:

| State | Meaning |
|-------|---------|
| **No controller** | Nobody is operating the device. Any assigned agent may take it. |
| **You have control** | You are the controller; your action buttons work. |
| **Another agent has control** | You are an **observer**; you must request access to operate. |

#### Controls related to handoff
- **Take Control** — appears when **no one** controls the device. Press it to become the
  controller. (If you try an action while the device is uncontrolled, you may be prompted
  to take control first.)
- **Request Access** — appears when **another agent** controls the device. It sends a
  request to the current controller, who sees an approval prompt.
  - The request **auto-expires after about 30 seconds** if the controller doesn't answer.
  - Possible outcomes (shown as pop-ups): **approved** (you get control), **denied**,
    **timeout** ("no response, you can request again"), **busy** ("another request is
    already pending"), or **superseded** ("device control was changed" — this can happen
    if a fleet manager forcibly reassigns control).
- **Incoming request prompt** — if you *are* the controller, you get a prompt when someone
  requests access, with **Approve** / **Deny** buttons and a countdown.
- **Release control** — frees the device so another agent can take it.

#### Observer banner
When you're an observer, a **banner** explains that another agent (named) is controlling
the device and that you are in read-only/observer mode. Pop-up notifications also announce
control changes (e.g. "Agent 'X' has taken control… you are now in observer mode").

---

### 7. The transaction session (gate for guest-facing actions)

Many guest-facing pages only work **during an active transaction session**. A transaction
session represents "one guest check-in/interaction at this kiosk".

#### Transaction-gated pages
These pages **require an active session** and will **send you back to the dashboard home**
if no session is running:

- Guest Details (/dashboard/guest-details)
- ID Scanner (/dashboard/scanner)
- Photo Capture (/dashboard/photo-capture)
- Cash Dispenser (/dashboard/cash-dispenser)
- Document Signature (/dashboard/legal-documents-fill)
- Key Dispenser (/dashboard/key-dispenser)
- Print / Receipt (/dashboard/print)
- Guest Rating (/dashboard/ratings)

Pages **outside** that list (Video Call, Message, Voice, Lights, Slideshow, Animation,
File Storage, Settings, Tasks, Transaction Reports, Receipt Designer, Legal Documents
library) are available **with or without** an active session.

#### Starting / stopping a transaction
- **Start Transaction** — begins a new session for the current device and agent. A live
  **elapsed timer** starts counting.
- **Stop Transaction** — ends the session manually.
- **Auto-timeout** — a session ends on its own after a set time (**default 30 minutes**,
  configured centrally). A pop-up warns "Transaction session timed out".
- **Auto-complete on key dispense** — when the kiosk reports that a room-key card was
  dispensed, the session is automatically marked **completed** ("Transaction completed —
  key dispensed").

#### Conflict dialog (session already exists)
If you try to start a transaction but one is already active (on this device, possibly
started by another agent), a **conflict dialog** appears with:
- **Connect to existing session** — reattach to the running session.
- **Close & start new** — end the existing one and start fresh.
- **Dismiss** — cancel.

#### Missing guest details dialog
After a session ends, if required guest fields (name, room number, account number, room
amount, deposit amount) are missing, a **"Missing guest details"** dialog prompts the
agent to fill them so the transaction record is complete.

---

### 8. Common status indicators (what colors/labels mean)

- **Online / green dot** — the kiosk is connected. Actions will be delivered.
- **Offline / red or grey** — the kiosk is not connected. Actions won't be delivered;
  wait for it to come back or refresh.
- **Observer / "another agent controlling"** — you can watch but not operate; use
  **Request Access**.
- **Pop-ups (toasts)** at the bottom of the screen — success/info/warning/error feedback
  for almost every action (action sent, control changed, session started/stopped, errors).
- **Disabled buttons** — usually mean one of: device offline, you don't have control, no
  active transaction session, an operation is already in progress, or you lack permission.

---

### 9. Universal troubleshooting checklist

When *anything* on the dashboard isn't working, walk this list (most issues are one of the
first three):

1. **Is the device Online?** Check the connection indicator. If Offline, the kiosk lost
   its connection — wait for it to reconnect or have someone check the kiosk.
2. **Do you have control?** If you're an observer, press **Request Access** (or **Take
   Control** if it's free). Actions from observers are silently blocked.
3. **Refresh the page.** This rebuilds the connection, re-syncs device status and control,
   and clears most "stuck" screens. (Most device pages also have their own
   **Refresh/Reconnect** control for the specific hardware — see each page.)
4. **Is a transaction session required?** Guest-facing pages (scanner, cash, key, print…)
   need an **active transaction**. If you were sent back to the dashboard home, start a
   transaction first.
5. **Re-select / switch the device.** Use the **Switch Device** button to drop and
   re-acquire the device if its control/session state looks wrong.
6. **Check the on-page recovery panel.** Device pages have recovery actions (reset, retry,
   reconnect hardware) — see the page's "Recovery & troubleshooting" section.
7. **Re-login.** If your sign-in expired or was revoked you'll be sent back to the login
   screen; sign in again.

See Part 4 for failure-specific recovery (cash jams, scanner re-initialization, key
dispenser errors, video-call recovery, etc.).

---

<a id="part2"></a>

## Part 2 — Agent Dashboard (Front-Desk Operator)

> This covers every page of the agent side (/dashboard/*). Read Part 1 first — it explains
> the concepts every page relies on: device online/offline, control vs. observer, and the
> transaction session gate. Where a page says "requires an active transaction" or "requires
> control", see Part 1 for what that means and how to fix it.
>
> Quick legend
> - Transaction-gated — only works during an active transaction session; otherwise
>   shows a "No active session" state or redirects to the dashboard home.
> - Control-gated — sending actions to the kiosk requires you to be In Control (not an
>   observer).
> - Pages talk to the kiosk over a live connection: the agent's clicks are sent to the
>   selected kiosk, which performs the action and reports status back. See section F,
>   "How buttons reach the kiosk".

---

### A. Global chrome (present on every dashboard page)

#### Global Top Bar (sticky header)
- Where: the sticky header across the top of every /dashboard/... page.
- Purpose: shows live connection/control status and holds the core session controls
  (Start/Stop Transaction, Take Control), the device switcher, and the account/logout
  menu. Because most feature pages need an active transaction and require control, this
  bar is where that state is managed.
- Controls:
  - Backend badge — top-left cluster — green "Backend" when your dashboard is
    connected to the server, red when not. Read-only.
  - Device badge — top-left cluster — green "Device" when the kiosk is online, red
    when offline. Read-only.
  - In Control / Observing badge — top-left cluster — green "In Control" if you
    operate the device, amber "Observing" if another agent does (hover shows who).
  - "Take Control" button — top-left cluster, only when you are NOT in control —
    requests control; shows "Request Pending…" and disables while a request is outstanding.
  - In Call badge — top-left cluster, conditional — green "In Call" with a pulsing
    dot when a video call is active on the kiosk.
  - Cashbox warning badge — top-left cluster, conditional — amber "Cashbox:
    notes/capacity" when near full, red when at/over capacity.
  - "Switch Device" button — top-left cluster, when a device is selected — drops the
    current device and returns you to device selection.
  - Transaction timer — top-right cluster, only during a session — counts up;
    green to yellow (about 66% of the timeout) to red (about 83%).
  - "Stop" button (red) — top-right, during a session — ends the current transaction.
    Disabled while loading or if you're not in control.
  - "Start Transaction" button (green) — top-right, when no session — begins a
    transaction. Disabled while loading, if no device is selected, or if you're not in
    control.
  - Avatar / account menu — far top-right — dropdown showing your agent ID
    (disabled item) and "Logout".
- Troubleshooting: if a feature page refuses an action, check this bar first — you
  most likely need to "Start Transaction" and/or "Take Control". A red "Device"
  badge means the kiosk is offline.

#### Left Sidebar (navigation)
- Where: fixed rail on the left (desktop); a hamburger menu at top-left opens it as a
  slide-out sheet on mobile.
- Purpose: primary navigation, split into a Transaction Features group (tools that
  only work during an active transaction) and a general list. Shows a task badge and an
  Observer-Mode control.
- Controls:
  - Transaction Features group (top) — "Guest Details (Alt+1)", "ID Scan
    (Alt+2)", "Photo Capture (Alt+3)", "Cash Dispenser (Alt+4)", "Document
    Signature (Alt+U)", "Key Dispenser (Alt+I)", "Print Receipt (Alt+O)", "Guest
    Rating (Alt+P)". These are greyed out and non-clickable when no transaction is
    active (header shows "(inactive)").
  - General nav list (below) — "Dashboard", "Tasks" (count badge; turns
    red/pulsing when tasks are overdue), "Video Call", "Transaction Reports",
    "SlideShow", "Animation", "Voice Over", "Message", "Receipts", "Legal
    Documents", "File Storage", "Indicator Lights", "Settings".
  - Observer Mode footer button (bottom, only when you're NOT in control) —
    requests control of the device; shows "Request Pending…" while outstanding.
  - Mobile hamburger (fixed top-left, mobile only) — opens the sidebar sheet.
- Keyboard shortcuts: Alt+1 through Alt+P jump to transaction items while a transaction is
  active.
- Troubleshooting: if transaction tools are greyed out, start a transaction from the
  top bar. Use the Observer-Mode footer to request control.

---

### B. Dashboard Home

#### Dashboard (Home / Overview)
- Route/URL: /dashboard
- How to reach it: "Dashboard" in the sidebar; it's also the default landing page
  after you log in and select a device.
- Purpose: an at-a-glance health/activity screen for the device you operate — backend
  and kiosk connection, cashbox total and note count, transaction count — plus a grid of
  shortcut tiles to every feature page.
- When an agent uses it: to confirm the device is connected before starting work; to
  check the cashbox quickly; as a launcher; to notice an in-progress video call (the
  Video Call tile shows a green "LIVE" badge).
- What happens: read-only. It shows live status (device/backend connection, cashbox
  summary, active video session, transaction count) that refreshes automatically. It
  also reacts to device alerts: a new-customer alert (toast plus alarm sound), room-key
  info, a "Cash device connected" notice, and any device error (red "Device error" toast).
- UI elements:
  - Status cards (5, top row) — read-only: "Backend" (Connected/Disconnected),
    "Device" (Connected/Not Connected), "Cashbox Total" ($), "Notes in Cashbox"
    (count/capacity, turns amber when near full), "Transactions" (count).
  - Feature tiles (grid) — clickable cards that navigate to: "Video Call", "Cash
    Dispenser", "Transaction Reports", "Key Dispenser", "Document Signature",
    "Transaction Report", "ID Scan", "SlideShow", "Animation", "Voice Over",
    "Guest Rating", "Print Receipt", "Message", "Settings".
  - "LIVE" badge — top-right of the Video Call tile only — appears during an active
    call.
- Troubleshooting: no recovery controls here. Backend "Disconnected" means the whole
  dashboard isn't getting live data (wait for reconnect). Device "Not Connected" means
  the kiosk is offline; actions on other pages will fail until it returns.

---

### C. Transaction-gated guest-facing pages

These pages only function during an active transaction session. They appear in the
sidebar's Transaction Features group and are greyed out until you press "Start
Transaction" in the top bar.

#### Guest Details [transaction-gated]
- Route/URL: /dashboard/guest-details
- How to reach it: sidebar → "Guest Details (Alt+1)".
- Purpose: record the single guest tied to the current transaction — name, account
  number, room number, currency, and room/deposit amounts. One guest per session; changes
  auto-save as you type.
- What happens: the form loads the current guest, then auto-saves shortly after you stop
  typing (about three-quarters of a second) once the name is non-empty and the form has
  changed. Nothing is sent to the kiosk. Saved data flows to other pages (Ratings, Cash,
  Print).
- UI elements (all in the card body; no Save/Cancel — saving is automatic):
  - "Guest Full Name" (required, red asterisk) — saving won't start until filled.
  - "Account No" — guest account number.
  - "Room No" — room number.
  - "Currency" — read-only, fixed to the session currency (e.g. USD).
  - "Room Amount" ($ number) — room/nightly charge.
  - "Deposit Amount" ($ number) — deposit held.
- States: without a transaction: "No active transaction session. Start a transaction
  to manage guest details." A blue banner notes "Only one guest can be added per session.
  Changes are saved automatically." A save indicator (top-right) shows "Saving…",
  "Saved" (green check), or "Save failed" (red). Card title is "Add Guest" (no guest
  yet) or "Guest Information".
- Troubleshooting: on failure the red "Save failed" indicator plus a toast appear; edit
  again to retry. If nothing saves, ensure the name is filled and a transaction is active.
- Related: Guest Rating, Cash Dispenser, Print Receipt (all use this guest).

#### ID Scanner (ID Scan) [transaction-gated]
- Route/URL: /dashboard/scanner
- How to reach it: sidebar → "ID Scan (Alt+2)"; or the "ID Scan" dashboard tile.
- Purpose: drives the kiosk's document scanner to capture a guest's ID (passport,
  driver's license, etc.), reads the details from it, shows the images/fields, and
  surfaces compliance alerts: under-age, Do-Not-Rent (DNR), and reservation name
  mismatch. A guest full name must be on file before scanning.
- What happens: "Start Scan" creates a scan job and tells the kiosk to begin scanning;
  "Cancel Scan" aborts it. Two-sided IDs automatically prompt for a second scan of side 2.
  The page listens for the kiosk's scan results and updates progress, the scanner-connection
  badge, and any DNR or name-mismatch alerts as they arrive. DNR and name-mismatch alerts
  must be acknowledged by the agent.
- UI elements:
  - Scanner Connected/Disconnected badge — header, by the title — "Scanner
    Connected", "Scanner Disconnected", or "Status Unknown".
  - Guest name display — header, top-right — the on-file name (read-only).
  - "Cancel Scan" button — header, top-right, only while scanning — cancels the active
    scan. Disabled while the cancel is pending.
  - "Start Scan" button — header, top-right — begins a scan (becomes "Scan Active…").
    Disabled because: a scan is already active, there's no active transaction, or no
    guest name is on file.
  - Progress banner — below header — "Scanning…", "Classifying…", "Running OCR…",
    "Uploading images…", "Completed".
  - Scanned Documents table — rows (Scan Job ID, Type, Status, Started At, Actions)
    with an "auto" badge, age badges ("Age Below 18" red / "Age Below 21" amber), and a
    "Reservation Mismatch" badge.
  - "View Details" (per row) — opens the full-screen Scan Details dialog (image plus tabs
    on the left, extracted fields/age-warning/alerts on the right). Shows "Extracting
    details…" while the details are still being read.
  - DNR Alert dialog — appears when a DNR match is pending; agent acknowledges.
  - Name Mismatch Alert dialog — appears when a reservation name mismatch is pending.
  - Guest Full Name Required overlay — full-screen blocking dialog when the session
    has no guest name; a required input plus "Save Guest" (also Enter).
- States: the table auto-refreshes every 10 seconds during a transaction. "No scanned
  documents for this session" / "No active session" empty states.
- Recovery & troubleshooting: "Cancel Scan" aborts a stuck scan (leaving the page
  while scanning also auto-cancels). If nothing could be read, the details dialog explains
  the document may be unreadable or the reading service unavailable. If a scan is already
  in progress, the page reuses that existing scan rather than failing.
- Related: guest name shared with Cash/Print; compliance alerts relate to Tasks and
  Transaction Reports.

#### Photo Capture [transaction-gated]
- Route/URL: /dashboard/photo-capture
- How to reach it: sidebar → "Photo Capture (Alt+3)".
- Purpose: triggers the kiosk camera to photograph the guest and stores it on the
  session; review captured photos in a full-screen zoom/pan viewer.
- What happens: "Capture Photo" creates a capture job and tells the kiosk to take the
  photo. When the kiosk reports success the list refreshes; on failure an error toast
  appears. The list also auto-refreshes every 10 seconds.
- UI elements:
  - "Capture Photo" button — header, top-right — triggers the capture ("Capturing…"
    while pending). Disabled because: a capture is in progress, or no active
    transaction.
  - Captures table — Capture ID, Status, Created At, Actions; error rows show the
    message inline.
  - "View" (per row) — opens the photo viewer (Zoom out/in, zoom %, "Fit larger" 2x,
    "Reset zoom"; mouse-wheel zoom, drag-pan, keyboard +/-/0).
- States: status badges "captured", "error" (red, with message), or raw status.
  Empty states "No captures for this session" / "No active session".
- Troubleshooting: a failed capture shows a red toast plus error row — just capture
  again. "No device connected" if the kiosk is offline.

#### Cash Dispenser [transaction-gated] [control-gated]
- Route/URL: /dashboard/cash-dispenser
- How to reach it: sidebar → "Cash Dispenser (Alt+4)"; or the "Cash Dispenser"
  tile.
- Purpose: collect cash from the guest (room charge plus optional deposit) through the
  kiosk's cash recycler/validator, then dispense change/refunds. Shows live recycler and
  cashbox contents, a running event log of every note collected/dispensed, denomination
  routing tools, and a recovery panel for stuck states.
- What happens: when the page opens it pulls the cash device and recycler info from the
  kiosk. Starting collection tells the kiosk to begin accepting notes toward the target
  amount; stopping ends collection (it also stops automatically once the collected amount
  reaches the target). Dispensing a refund or a custom amount tells the kiosk to pay out.
  Denomination routes are saved and then sent to the device. Recovery actions (including
  "Clear Transaction") are described in the Recovery Panel widget below. The live event
  log, totals, and connection state all update from the kiosk's reports.
- UI elements:
  - Connected/Disconnected badge — top-right of the header — cash device connection.
  - Recovery panel — below the header — recovery actions including "Clear Transaction"
    and a button that opens the "Denomination Routes" dialog (details in
    the widget section).
  - Guest dropdown — Guest Details card — which guest to bill; disabled during
    cash-in or with no guests.
  - "Guest Name" (required), "Room No", "Room Amount" (required, numeric), "Deposit
    Amount" (numeric) — Guest Details card — auto-sync to the session; disabled during
    cash-in.
  - "Cash-In Amount" summary — read-only "Room + Deposit" total.
  - "Start Cash-In" button — Guest Details card footer — begins collection.
    Disabled because: device disconnected, no session, mid-dispense, currently
    dispensing, guest name empty, or room amount not greater than 0.
  - "Stop Cash-In" button (red) — replaces Start while collecting.
  - Cash Events list — running log (timestamp, color-coded type, amount).
  - "Cash-In Amount" / "Collected" / "Refund Due" (or "Remaining" / "Over-dispensed") tiles —
    read-only running totals.
  - "Dispense Refund" button — Cash Events card footer — dispenses the computed refund;
    "Dispensing…" while busy. Disabled because: disconnected, already
    dispensing, refund due 0 or less, or no session.
  - "Dispense Custom Amount" button — opens the custom dispense dialog. Disabled when
    disconnected, dispensing, or no session.
  - Recycler/Cashbox table plus info tooltip — per-channel/recycler contents and totals;
    the info icon warns totals can be inaccurate if a recycler's denomination changed
    while it still held old notes. Below: Cashbox Note Count, Total Amount, and Fill
    Level % (green/yellow/red).
  - "Denomination Routes" dialog (from the Recovery panel) — Currency (USD) plus per-
    recycler/per-payout numeric inputs (Recycler 1–4 for NV4000; Payout 1–7 for NV200);
    "Close" and "Save & Send to Device".
  - "Dispense Custom Amount" dialog — Amount input; "Cancel" / "Dispense" leads to a
    "Confirm Dispense" dialog ("This action cannot be undone") with "Confirm Dispense".
- States: "No active session" empty card; "No events yet" / "No recycler data".
  Collected tile turns green when target met. Disconnect shows a red toast and clears
  recycler/cashbox data. Buttons are disabled mid-dispense to prevent overlapping payouts.
- Recovery & troubleshooting: the Recovery panel is the main recovery surface
  (Clear Transaction, return escrow, halt payout, reset device, reload routes,
  COM re-attempt). Cash-in auto-stops at the target. See Part 4.
- Related: guest details shared with Print; cashbox totals also appear on the Home
  page and top bar.

#### Document Signature (Legal Documents – Fill) [transaction-gated] [control-gated]
- Route/URL: /dashboard/legal-documents-fill
- How to reach it: sidebar → "Document Signature (Alt+U)".
- Purpose: the live tool to push a legal-document template to the kiosk for the guest
  to fill in and sign during a transaction. Pick a template, optionally pre-fill fields,
  send it to the kiosk, then watch progress, remotely capture, or close it, and review the
  finished signed PDFs.
- What happens: requires an active session. On Send it optionally stores your pre-fill
  values, then pushes the chosen template to the kiosk. "Capture Document" tells the kiosk
  to capture the signed document; "Close Document" cancels it on the kiosk. The kiosk
  reports back ("COMPLETED"/"CANCELLED"/"ERROR") and the submissions list refreshes when a
  document is completed.
- UI elements:
  - Template dropdown — only templates that have at least one field appear; otherwise
    "No templates with fields available. Create templates in Legal Documents."
  - Pre-fill field inputs — appear when the template has non-signature fields (text,
    date, checkbox). Signature fields are never pre-fillable.
  - "Send to Kiosk" button — pushes the document. Disabled because: no template
    selected, no active transaction, or you lack the Send-to-Kiosk (document fill)
    permission. On success reveals Capture/Close.
  - "Capture Document" button — appears after a document is open; tells the kiosk to
    capture/scan it.
  - "Close Document" button (red) — appears after a document is open; cancels it on the
    kiosk.
  - "View Details" (per submission) — opens the signed PDF (only for "completed"
    submissions with a PDF).
- States: a "Kiosk:" line echoes the latest kiosk message for live progress. Without a
  transaction: "Start a transaction first…" and Send disabled. Submission status badges:
  completed / failed (red) / other.
- Troubleshooting: "No active transaction" / "Select a template first" / "Failed to
  store pre-fill values" (send aborted — retry). On an error or cancellation the open
  panel closes and the list refreshes; resend if needed.
- Related: "Legal Documents" plus "Field Editor" (create templates), "File Storage"
  (source PDFs).

#### Key Dispenser [transaction-gated]
- Route/URL: /dashboard/key-dispenser
- How to reach it: sidebar → "Key Dispenser (Alt+I)"; or the "Key Dispenser" tile.
- Purpose: controls the kiosk's RFID room-key card dispenser — connect, monitor
  hardware status (device/transport/card-box/recycle), move cards (read position,
  dispense, eject, capture/recycle), enable/disable front insertion, and run resets. A
  live event log records every action and reply.
- What happens: the page tries to connect to the dispenser when it opens. Buttons send
  their actions to the kiosk (connect, disconnect, request info/status, move/dispense/eject/
  capture a card, enable/disable front entry, and the various resets), and the kiosk's
  replies update the badges and log. When auto-poll is on, the page requests status every
  3 seconds. Note: a successful dispense automatically completes the transaction session.
- UI elements:
  - "Connect" button — Connection card — connects to the dispenser. Disabled when
    already connected.
  - "Disconnect" button (red) — disconnects. Disabled when not connected.
  - "Info" button — requests device info / COM port.
  - Auto-poll switch — Device Status card header, top-right — polls status every
    3 seconds. Disabled when not connected.
  - "Refresh Status" button — requests status once. Disabled when not connected.
  - Movement: "Move to Read Position", "Dispense to Front", "Eject from Bayonet",
    "Capture / Recycle". All disabled when not connected.
  - Front Entry: "Enable Front Entry", "Disable Front Entry".
  - Recovery: "Reset Device", "Reset (Keep Card)", "Reset → Issuing Box",
    "Reset → Recycle Box".
  - "Clear" button — Event Log header — clears the on-page log (local only).
- States: connection dot (disconnected/connecting/connected) plus COM port; four
  status badges — "Device" (Idle/Fault/Sending/Retaining…), "Channel"
  (Overlap/Jam/Card Present/No Card/Card Entering), "Card Box" (Empty/Low/Sufficient/
  Not Full/Full), "Recycle" (Not Full/Full); "--" when unknown. Log entries color-coded
  CMD/INFO/WARN/ERR.
- Recovery & troubleshooting: the four "Reset" buttons handle jams/faults. If the
  device disconnects, all actions disable — press "Connect" (or reopen the page to
  auto-reconnect). Errors appear as red ERR log entries.

#### Print Receipt [transaction-gated] [control-gated]
- Route/URL: /dashboard/print
- How to reach it: sidebar → "Print Receipt (Alt+O)"; or the "Print Receipt" tile.
- Purpose: prints a receipt at the kiosk using the device's active receipt design.
  Auto-fills variables (hotel info from device options; guest info from the session), lets
  you pick the guest and printer, edit remaining fields, and send the job.
- What happens: the page loads the active receipt design and the list of available
  variables. Listing the kiosk's printers requires being In Control. Printing sends the
  filled-in receipt (design layout, variable values, paper type, auto-cut setting, and the
  chosen printer name) to the kiosk, which prints it and reports back "SUCCESS",
  "FAILED", or an error.
- UI elements:
  - "Refresh Printer Options" button — Printer row, top-right — re-fetches the kiosk's
    printers. Disabled because: not in control, or while refreshing/loading.
  - Printer dropdown — "Default (Windows default printer)" or a named printer.
  - Guest dropdown — pick a guest to auto-fill, or "Manual Entry".
  - Variable inputs (grid) — one per required variable; kiosk-time variables are
    disabled ("Kiosk system time will be used"). Editing a session-sourced field syncs it
    back to the guest.
  - "Print Receipt" button — sends the job. Disabled because: a required
    (non-kiosk-time) variable is still empty.
- States: if no active design exists, an alert card says "No active receipt design
  found for this device" and points to "Receipts". A helper line explains why the
  printer list is empty (loading / not in control / kiosk returned none) — in those cases
  printing falls back to the kiosk's default printer.
- Troubleshooting: if the printer list is empty, take control and click "Refresh
  Printer Options" (you can still print to default). Print failures show "FAILED" or
  error toasts. No active design means you should create/activate one under "Receipts".

#### Guest Rating [transaction-gated] (rating prompt) / always-available (slideshow card)
- Route/URL: /dashboard/ratings
- How to reach it: sidebar → "Guest Rating (Alt+P)" / "Ratings".
- Purpose: prompt the guest to leave a star rating on the kiosk and review ratings
  received during the active transaction; also play any slideshows marked "Guest Rating
  Slideshow". The rating-prompt area needs an active transaction; the slideshow card is
  always visible.
- What happens: "Show Rating Screen" tells the kiosk to display the rating prompt for
  the chosen guest/account and timeout. Existing ratings load automatically; when the
  guest finishes rating, the kiosk reports it and the list refreshes ("New rating
  received"). If the guest doesn't respond in time, you see "Guest rating timed out". The
  slideshow "Play" tells the kiosk to display the selected images (never looping); "Stop"
  hides them.
- UI elements:
  - Guest dropdown — header (only with an active transaction) — which guest/account
    the rating is for; disabled when there are no guests.
  - "Timeout (s)" — header — how long the rating screen stays up (default 10).
  - "Show Rating Screen" button — sends the prompt.
  - Ratings table — read-only received ratings (ID, account, 1–5 stars, date/time).
  - Guest Rating Slideshows rows — each with "Play" / "Stop".
- States: without a transaction the prompt is replaced by "No active transaction
  session…". Empty states for ratings and for guest-rating slideshows ("Mark a slideshow
  as 'Guest Rating Slideshow' on the Slideshow page").
- Related: "Slideshow" (flag configs), "Guest Details" (guest/account list).

---

### D. Always-available pages (work with or without a transaction)

#### Video Call [control-gated]
- Route/URL: /dashboard/video-call
- How to reach it: sidebar → "Video Call"; or the "Video Call" tile (shows
  "LIVE" during a call).
- Purpose: start and manage a Google Meet call on the kiosk so the agent can talk
  to the guest face-to-face, then control what the guest sees on the kiosk screen.
- What happens: "Start Video Call" opens the meeting on the kiosk and applies a set of
  display overlays. If there's already a call, force-starting ends the existing one and
  starts the new one. "End Call" ends the call on the kiosk. Display-option toggles are
  sent to the kiosk to control the overlays and screen layout, and the call status badge
  updates from the kiosk's reports. If the guest asks for assistance, the page plays a
  sound and shows a browser notification.
- UI elements:
  - Video Call URL or Code input — paste a Meet link or code. Disabled once a call is
    active or a conflict is showing.
  - Guest Name input — name shown for the kiosk participant ("Front Desk Kiosk").
  - "Start Video Call" button — Disabled because: URL or name is empty, or a
    conflict is pending.
  - "Retry Call" plus "Cancel" buttons — appear only after a "denied" status; Retry
    force-starts.
  - "End Call" button (red) — ends the call.
  - "Join Call as Agent" button — opens the meeting link in a new browser tab for the
    agent.
  - "Active Session Detected" conflict card — "Cancel" / "End Previous & Start
    New" (force-start).
  - Kiosk Display Options (toggles, during a call only):
    - "Hide Call Controls" — covers the Meet toolbar.
    - "Show Hotel Name" — hotel banner at the top.
    - "Hide Video Call Display" (only with the Hide-Video-Call-Display permission) —
      hides the video so animations/slideshow fill the screen while audio continues.
    - "Fill Screen With Video" — agent's video covers the kiosk screen; if the agent
      camera is off, shows the agent's photo plus name.
    - "Show Captions" — turns captions on.
- States: status badge: "No active call", "Joining call…", "Waiting for host to
  admit", "In call", "Join request denied", "Retrying join…", "Removed from call",
  "the video window crashed and is recovering", "Call ended", or "Error". Some toggles
  may be enforced (kept on) depending on device configuration and auto-revert about 60
  seconds after being switched off (while in control). A 10-second reconnect grace
  ignores spurious removed/ended status right after (re)connecting.
- Recovery & troubleshooting: denied leads to "Retry Call"; existing session leads to
  "End Previous & Start New"; a kiosk display crash auto-recovers. Invalid links show
  "Invalid video call URL or code." A guest-assist alert (sound plus notification) asks
  the agent to enable the video display.

#### Message [control-gated]
- Route/URL: /dashboard/message
- How to reach it: sidebar → "Message".
- Purpose: put text on the kiosk screen for the guest and collect typed replies. Three
  areas: "Show Message" (display text with font size, language, auto-hide timeout),
  "Capture Message" (prompt the guest to type and show replies), "Message Presets"
  (reusable one-click messages).
- What happens: "Show Message" displays your text on the kiosk (with the chosen font
  size, language, and timeout); "Hide Message" clears it. "Show Message Input" prompts the
  guest to type a reply (with an idle timeout); "Hide Input" removes the prompt. Guest
  replies arrive live (the most recent ~20 are kept), and existing replies load when the
  page opens. Presets are saved for reuse.
- UI elements: "Message" textarea (max 250, live counter), "Font Size", "Language"
  (EN/ES/FR/DE/IT/PT/NL), "Timeout (s)"; "Show Message" / "Hide Message". Capture
  card: "Input Idle (s)", "Show Message Input" / "Hide Input", "Copy" per reply.
  Presets card: "Add Preset", preset form (Message/Language/Font/Timeout), "Save" /
  "Update" / "Cancel"; click a preset card to send it instantly; "Edit" / "Delete"
  per preset.
- States: amber warning in Capture when no transaction is active ("guest messages will
  not be saved"); each unsaved reply is flagged. Empty states for responses and presets.
- Troubleshooting: messages over 250 chars are blocked. If replies aren't saved, start
  a transaction first. Sending needs the kiosk connected.
- Related: "Voice Over" (audio equivalent, same preset pattern).

#### Voice Over [control-gated]
- Route/URL: /dashboard/voice
- How to reach it: sidebar → "Voice Over".
- Purpose: make the kiosk speak text aloud (text-to-speech) in a chosen language.
- What happens: "Speak" tells the kiosk to read your text aloud in the chosen language.
  Presets are saved for reuse; there's no stop button and no reply from the kiosk.
- UI elements: "Text" textarea (max 250, counter), "Language" (EN/DE/FR/ES/IT/NL/
  PT/Arabic/Chinese/Japanese), "Speak" (disabled when empty); "Add Preset", preset
  form (Text/Language), "Save" / "Update" / "Cancel"; click a preset to speak it;
  "Edit" / "Delete" per preset.
- Troubleshooting: text over 250 chars is blocked; empty text can't send; speaking
  needs the kiosk connected.

#### Animation [control-gated]
- Route/URL: /dashboard/animation
- How to reach it: sidebar → "Animation"; or the "Animation" tile.
- Purpose: a board of pre-built guidance animations to flash on the kiosk to visually
  instruct the guest. One click plays; one button hides.
- What happens: clicking an animation tells the kiosk to play that animation; "Hide
  Animation" clears it. Each click shows a toast.
- UI elements: "Hide Animation" (red) — header, top-right; 12 animation cards:
  1 Tap For Assistance, 2 Assistance on Wait, 3 ID Scan, 4 Cash In, 5 Credit Card Tap,
  6 Credit Card Swipe, 7 Credit Card Chip, 8 Processing Room Key, 9 Collect Room Key,
  10 Collect Room Receipt, 11 Collect Cash Receipt, 12 Appreciate Your Patience.
- Troubleshooting: no error banners. If an animation doesn't appear, the device may be
  offline. Press "Hide Animation" to clear a stuck animation, then re-send.

#### Slideshow [control-gated]
- Route/URL: /dashboard/slideshow
- How to reach it: sidebar → "SlideShow"; or the "SlideShow" tile.
- Purpose: build and play image slideshows on the kiosk. Select images from File
  Storage, order them (drag/arrows), set a per-image timer and optional loop, then play on
  the kiosk or save as a reusable configuration. Configs can be flagged "Guest Rating".
- What happens: "Play on Kiosk" tells the kiosk to display the selected images at the
  chosen timer and loop setting; "Stop" hides them. Configurations and storage images are
  saved and loaded automatically.
- UI elements: Editing badge plus X (clears the loaded config); "Play on Kiosk",
  "Stop", "Save" (header cluster); "Image Timer (s)" (1–86400), "Loop slideshow"
  checkbox; Selected Images list (drag handle, Up/Down arrows, Remove X); "Select
  All"/"Deselect All"; clickable storage image cards; saved-config cards (click to load;
  per-card "Play" / "Delete") with badges (count, timer, "Guest Rating"/"Loop");
  "Save Configuration" dialog (Update existing / Name for new / Guest Rating checkbox /
  Loop checkbox / Save as New); "Delete Configuration" dialog.
- Troubleshooting: "Select at least one image" when saving/playing with nothing
  chosen; "No images in this configuration" for an empty config. Playing needs the kiosk
  connected.
- Related: "File Storage" (image source), "Guest Rating" (plays "Guest Rating"
  configs).

#### Indicator Lights [control-gated]
- Route/URL: /dashboard/lights
- How to reach it: sidebar → "Indicator Lights".
- Purpose: control the kiosk's external indicator-light board (up to 12 channels):
  see which are on, toggle individual channels, all on/off, and watch a live event log. If
  the device has no light hardware, the page shows a disabled notice.
- What happens: the page requests the current light status when it opens. Toggles turn
  an individual channel on or off; "All ON"/"All OFF" switch every channel; "Refresh"
  re-requests the status. The kiosk's replies update the toggles, the indicator, and the
  log. Channel names come from a label mapping configured centrally (falling back to
  "Channel N"), and whether the page is enabled depends on the device's indicator-lights
  setting.
- UI elements: "Refresh" (Status card header), "All ON" / "All OFF" (Output
  Controls header; disabled when disconnected), per-channel toggles (disabled when
  disconnected), "Clear" (Event Log header), "Go to Settings" (only when lights are
  set to "none").
- States: "Indicator lights are disabled for this device…" when the indicator-lights
  setting is "none"; Status dot Connected/Disconnected plus "X / 12 ON" badge; all
  controls disabled while disconnected; log color-coded CMD/INFO/WARN/ERR.
- Troubleshooting: if Disconnected, press "Refresh" (the log notes "IO board
  disconnected" / "Status synced"). Generic "Channel N" names mean the label mapping isn't
  configured. If the page is disabled, enable lights in "Settings".

#### Legal Documents (template library)
- Route/URL: /dashboard/legal-documents
- How to reach it: sidebar → "Legal Documents".
- Purpose: build reusable signature templates from uploaded legal PDFs. Lists every
  template (with field count) and lets you turn a legal PDF into a new template. Templates
  are what guests later fill and sign on the kiosk (via Document Signature).
- What happens: the page loads your templates and the legal PDFs in storage. Creating a
  template makes a new one and takes you straight to the field editor; deleting removes the
  template. Nothing is sent to the kiosk from this page.
- UI elements: "Edit" (pencil) / "Delete" (trash) per template row (disabled
  without template-edit permission); "+ <file name>" buttons under "Legal document
  PDFs without templates" (only when unlinked legal PDFs exist plus you have edit
  permission); "Create Template" dialog (Template Name; "Cancel" / "Create & Edit
  Fields"); "Delete Template" dialog ("The PDF file will remain in storage").
- States: field-count badge (highlighted when greater than 0, muted at 0 = not ready);
  empty state points to File Storage.
- Related: "File Storage" (upload the PDF first), "Field Editor", "Document
  Signature".

#### Legal Document Field Editor
- Route/URL: /dashboard/legal-documents/[id]
- How to reach it: "Edit" on a template row, or "Create & Edit Fields" after
  creating a template. Not a standalone sidebar item.
- Purpose: a visual PDF editor for placing the fields a guest fills in — drop text,
  signature, date, and checkbox fields onto exact PDF positions, drag/resize them, and set
  per-field properties. Saving stores the layout for sending to a guest.
- What happens: the page loads the template and its PDF. Field positions are stored
  relative to the page so they scale to any kiosk screen. Save stores the layout; Delete
  removes the template. Nothing is sent to the kiosk.
- UI elements: "Back" arrow; Template name input; page-count text; "Delete"
  (red) / "Save" (disabled when no unsaved changes or without edit permission);
  "Text" / "Signature" / "Date" / "Checkbox" tool buttons; PDF canvas (click to drop a
  field; drag to move; resize handles); Fields list (right panel); per-field
  "Label", "Required", "Placeholder", "Max Length" (text), "Default to Today"
  (date), "Checked by Default" (checkbox), "Delete Field"; Esc deselects.
- Troubleshooting: "Failed to load PDF" means you should confirm the file still exists
  in File Storage. Back does NOT auto-save — Save first.

#### File Storage
- Route/URL: /dashboard/storage
- How to reach it: sidebar → "File Storage".
- Purpose: the kiosk's media library. Upload/manage images (JPG/PNG) and PDFs, tagged
  as normal files or legal documents. Images feed Slideshows; legal PDFs become signature
  templates. Includes preview, category filtering, and safe deletion with slideshow-usage
  warnings.
- What happens: files load when the page opens. Uploads run a few at a time and retry
  on failure. Before deleting, the page warns if an image is used in any slideshow config.
  Adding/deleting general files and legal documents each require their own permission.
  Nothing is sent to the kiosk.
- UI elements: Category dropdown (Normal File / Legal Document — the latter only
  with the legal-document add permission); "Upload" (disabled without add permission;
  legal accepts only PDF); "All" / "Files" / "Legal Documents" filters; file card
  thumbnail (opens preview; PDFs in an embedded viewer); "Delete" (trash) per card;
  "Delete File" dialog (warns if the image is the only image in a slideshow config);
  floating Upload Queue panel (retry / retry-all / cancel-all / remove / clear-finished /
  close).
- States: "Max file size: 10 MB. Supported: JPG, PNG, PDF." Oversized/wrong-type files
  are skipped with a toast. Legal documents get an amber "Legal" badge.
- Troubleshooting: a permission error on delete shows "You don't have permission…
  Contact your administrator." Failed uploads can be retried from the queue panel.
- Related: "Slideshow", "Legal Documents" plus "Field Editor", "Document Signature".

#### Receipts — Receipt Designer (list)
- Route/URL: /dashboard/receipt-designer
- How to reach it: sidebar → "Receipts" (Receipt Designer). Requires a selected
  device.
- Purpose: manage the kiosk's receipt layouts — create, activate, duplicate, edit, and
  delete designs. The active design is what the kiosk prints (used by Print Receipt).
- What happens: actions (list, create, activate, deactivate, delete, duplicate) apply
  to the selected device's designs. Each action checks your permission; without it you see
  "You don't have permission… Contact your administrator."
- UI elements: "New Design" (top-right, disabled without the add-design permission);
  "Create First Design" (empty state); Designs table (Name, Paper badge
  80mm/58mm, Blocks count, Created, Active toggle, Actions). Per row: Active toggle
  (activate/deactivate; disabled without the activate permission), "Edit" (disabled
  without the edit permission), "Duplicate" (disabled without the add permission),
  "Delete" (red, disabled without the delete permission) leading to a Delete confirmation
  dialog.
- Troubleshooting: greyed buttons mean a missing permission (contact your
  administrator); "No device selected" means choose a device.
- Related: the Editor (below); printed receipts appear in Session Command Events on
  Transaction Reports.

#### Receipts — Receipt Designer (editor)
- Route/URL: /dashboard/receipt-designer/[id]
- How to reach it: from the list via "New Design", "Edit", or after creating.
- Purpose: a drag-and-drop builder for a single receipt layout with a live,
  paper-accurate preview — compose blocks, insert {{Variable}} placeholders, pick paper
  width, and save.
- What happens: the design loads (cleaning up its blocks on load), and text is stripped
  of characters a thermal printer can't handle. Save stores the name, paper type, blocks,
  and kiosk-time settings; a logo can be uploaded. The preview is shown on screen only — it
  does NOT print.
- UI elements: "Back"; Design name input; Paper type select (80mm/58mm,
  changes preview width; an "Active" badge shows if this is the active design);
  "Delete" (red); "Save" (disabled when saving / no unsaved changes / without
  the edit permission); "Add Block" dropdown (Text, Separator, Spacer, Key-Value, QR
  Code); sortable block rows (drag handle, expand/collapse, Move up/down, Delete);
  per-block config (Text: content plus Variable plus Alignment plus Font Size plus Bold;
  Separator style; Spacer lines; Key-Value; QR Code; Image upload; Barcode);
  "Use kiosk system time for {{Date}}/{{DateTime}}" toggle; Variable picker
  popover; sticky Preview panel; Delete confirmation dialog.
- Troubleshooting: Back doesn't save — Save first. Save stays disabled until you make a
  change (or if you lack edit permission). Logo upload failures toast "Upload failed".

#### Transaction Reports
- Route/URL: /dashboard/transaction-reports
- How to reach it: sidebar → "Transaction Reports"; each row links to its detail
  page. Scoped to your selected device.
- Purpose: a searchable, paginated audit log of all cash/transaction sessions that ran
  on the selected kiosk — the operator's record of each guest interaction (cash, receipts,
  key dispensing, legal docs, photos, ratings, AI audit).
- What happens: read-only; the report is always re-fetched fresh. "Export XLSX"
  downloads the filtered set as a spreadsheet file named for the device. The filters live
  in the page's address so the view is shareable and survives back-navigation.
- UI elements:
  - "Export XLSX" — top-right header — exports the whole filtered set (respects dates,
    not pagination).
  - "Start Date" / "End Date" — filter row — auto-apply on change, reset to page 1.
  - "Search" button — re-runs the query (resets paging).
  - "Real transactions only" checkbox — default ON; uncheck to include sessions with
    no activity.
  - "Total" — read-only count.
  - Sessions table — "Session ID" (first 8 chars plus "…"), "Agent ID", "Status"
    badge, "Date/Time" (local timezone). Each row links to the detail page. A "Last
    viewed" eye badge marks the last session you opened; a "No activity" badge marks
    sessions with no real interaction.
  - Pagination — 20 rows/page; auto-jumps to the last valid page if the current page
    exceeds the total.
- States: status badge: completed (neutral), ongoing (grey), other/error (red). "No
  sessions found" when filters return nothing.
- Troubleshooting: data is never cached (always fresh). A long-"ongoing" status means
  the session never closed cleanly on the kiosk. Export failure shows a toast; retry and
  confirm a device is selected.

#### Session Details (Transaction Report detail)
- Route/URL: /dashboard/transaction-reports/[sessionId]
- How to reach it: click any row in Transaction Reports. Carries the list's filters
  forward.
- Purpose: a full read-only dossier for one session — metadata, guest info, cash
  summary, agent, rating, AI audit, guest message inputs, every cash event, every command
  event, legal-document submissions, and photo captures.
- What happens: read-only. Prev/Next move across session boundaries within the current
  filtered set. Opening a session records it as your "last viewed".
- UI elements: "Back to Transaction Reports" (preserves filters); Record
  navigation (Prev/Next plus position counter; arrows disable at the ends); "Retry" (on
  load error); per-row "View Details" on Legal Documents (signed PDF dialog, only for
  "completed" with a PDF) and "View" on Photo Captures (image dialog, only for
  "captured").
- Sections (read-only): Details (session, guest info, cash summary, agent, rating,
  AI audit), Guest Message Input, Cash Events (color-coded types: green
  STACKED/STORED accepted, red DISPENSED/RETURNED/fraud, yellow ESCROW, orange
  DISPENSING), Session Command Events (Print Receipt / Key Dispenser / Show Message /
  Voice Over with action plus details), Legal Documents, Photo Captures.
- Troubleshooting: Retry on load failure. Missing End Time / long "ongoing" means the
  session never closed on the kiosk. Red fraud-attempt event types flag rejected/suspect
  notes.

#### Tasks
- Route/URL: /dashboard/tasks
- How to reach it: sidebar → "Tasks" (the count badge points here).
- Purpose: the operator's to-do list for the current device — assigned tasks
  (one-time and recurring) with deadlines and priority, overdue highlighting, and a detail
  dialog to write a response, attach images, save a draft, and submit. Editing/submitting
  requires control of the device (else read-only observer mode).
- What happens: tasks load and refresh every 30 seconds. While you have control, your
  draft auto-saves shortly after you stop typing; submitting sends the final response.
  Images upload through a queue. Tasks are sorted by priority then overdue-first.
- UI elements: "Open Task" per card leads to a Task detail dialog (can't be dismissed
  by clicking outside/Escape): "Add images" (JPG/PNG/WEBP up to 10 MB), image thumbnails
  (preview plus delete), "Your response" textarea (auto-saves with control), "Save"
  (disabled without control / while saving / no changes), "Submit" (disabled without
  control / empty response / while submitting / while images upload). Floating Upload
  Queue panel.
- States: amber banner when you don't have control ("Take control… to save or
  submit"). Badges: priority (urgent=red), status, kind (Recurring/One-time); overdue
  cards get a red ring plus "Overdue". "Saved <time>" indicator; image counter "used/max";
  "Last edited by <agent>" if a different agent touched the draft.
- Troubleshooting: take control to edit. "Response cannot be empty" / "Wait for image
  uploads to finish before submitting." Failed uploads retry from the queue panel.

#### Settings (device configuration)
- Route/URL: /dashboard/settings
- How to reach it: sidebar → "Settings"; also the "Go to Settings" button on the
  Indicator Lights page when lights are disabled.
- Purpose: the master configuration page for the kiosk device — hotel/network/schedule
  info, connected hardware (cash and key ports, scanner, OCR, indicator lights, cash
  dispenser), cash-denomination routing, and cashbox status/capacity. Changes are grouped
  into three independently-saved sections.
- What happens: the device's current settings load when the page opens. Each section
  saves on its own — Device Options, Cash Routes (the routing fields differ by dispenser
  type), and Cashbox (including a reset to zero). Each save checks required fields and
  scrolls to the first invalid one.
- UI elements:
  - Device Options card: Hotel Name, Support Email, Phone, WiFi Name, WiFi Password,
    Check Out Time, Breakfast Time (all required); Cash Port / Key Port (COM0–COM11), Baud
    Rate; "Cash Dispenser Type" (NV4000/NV200 — switches the routes section below);
    "Scanner Option" (SINOSECU_LOCAL/OLD); "OCR Option" (InHouse / InHouse Cloud /
    GuestBan — GuestBan disabled with "(key not configured)" until the integration key
    is set); "Indicator Lights" (U10/None — None disables the Lights page);
    "Simulation Mode" toggle (only with the Simulation-Mode permission); Body Notes,
    Footer Notes; "Save Options" button.
  - Cash Denomination Routes card (title shows the dispenser type): Currency; Recycler
    1–4 (NV4000) or Payout 1–7 (NV200); "Save Routes".
  - Cashbox Status card: Cashbox Capacity, Note Count, Total Amount ($); "Reset
    Cashbox to Zero" (confirmation dialog); "Save Cashbox".
- States: each card shows an amber "Unsaved changes" badge when its values differ from
  saved. Required fields marked with a red asterisk; invalid fields highlighted.
- Troubleshooting: saving with missing fields shows "Please fill N required field(s)…"
  and the view scrolls to the first invalid field. For GuestBan OCR, the integration key
  must be configured centrally before it can be selected here.
- Related: "Indicator Lights" (enabled/typed here); cash features (routes plus cashbox).

---

### E. Shared widgets, banners & dialogs

These appear across many device pages (not as standalone sidebar items).

#### Quick Actions (floating button)
- Where: a floating circular lightning-bolt button fixed at the bottom-right
  of device pages. Click it or press Ctrl+K / Alt+K / Cmd+K to open a popover above
  it.
- Purpose: a one-stop "do something on the kiosk right now" panel for on-screen
  messages, text-to-speech, animations, slideshows, and indicator lights.
- Tabs & controls: "Message" (presets plus Custom mode: textarea/Size/Timeout/Language;
  "Send" / "Hide"), "Voice" (presets or custom text plus Language; "Speak"),
  "Animation" (12-animation grid plus "Hide Animation"), "Slideshow" (saved configs to
  play, plus "Stop"), and "Lights" (only if the device has lights: connection dot plus
  "n/12 ON", per-channel on/off, "All ON" / "All OFF").
- Observer gating: if you don't have control, an amber "Observer mode — take control to
  use actions" strip appears and all inputs/buttons are disabled.
- Recovery relevance: the "Hide" buttons clear stuck on-screen content
  (message/animation/slideshow). A red Lights dot means the light controller is
  disconnected.

#### Recovery Panel (cash-device page)
- Where: a "Recovery & Diagnostics" card on the Cash Dispenser page; risky actions
  are behind a collapsible "Advanced Recovery & Diagnostic Options" section.
- Purpose: the toolkit for fixing a misbehaving cash recycler/validator — an
  escalation ladder from safest to most drastic.
- Controls (each with a tooltip explaining what it does and why it might be disabled):
  - "Set Denomination Routes" — opens the routes dialog.
  - "Clear Transaction" — resets the host-side transaction state only (fixes a
    page that thinks a transaction is active when the device is fine).
  - "Refresh" — re-pulls device info/recycler counts; disabled when offline.
  - Status badges — Connected/Disconnected, "State" (red if ERROR/JAM_RECOVERY),
    "Tx" (current transaction state plus amount), "Last Event".
  - Advanced → Quick Recovery: "Return Escrow" (only when a note is in the bezel),
    "Halt Payout" (only during an active dispense).
  - Advanced → Device Recovery: "Reset Device" (soft firmware reboot — confirmation
    dialog), "Reload Routes" (disabled during an active transaction), "Device COM
    RE-Attempt" (red, closes and reopens the comm port — confirmation dialog, last resort).
- Escalation order: Clear Transaction → Refresh → Return Escrow/Halt → Reset Device →
  Reload Routes → COM Re-Attempt. Reset and Reconnect cancel active transactions
  (escrowed bills may need manual return).

#### Control Request Dialog (you hold control, someone asks)
- Where: a modal that pops up for the agent who currently controls a device when
  another agent requests it.
- Controls: "Approve" (hand control to the requester; you become observer), "Deny"
  (they keep observing; closing the dialog = Deny), and a 30-second auto-deny
  countdown.
- Concept: control is never silently stolen — the holder must approve.

#### Request Access Dialog (you're an observer, you want control)
- Where: a modal shown when you click "Take Control" but another agent holds it.
- Controls: "Request Access" (sends a request to the holder, then "waiting for X to
  respond", auto-closes after about 1.2 seconds with a toast), "Cancel".
- Concept: the sanctioned path to gain control; then watch the Observer Banner for the
  response/countdown.

#### Kiosk Alert Banner (screen-blocked warning)
- Where: a thin red banner across the top of device pages, shown only when the
  kiosk reports its screen is not visible to the guest (another window is on top of the
  kiosk app).
- Recovery relevance: signals a foreground-window problem on the kiosk — bring the
  kiosk app back to front (or escalate) so the guest can see the screen.

#### Observer Banner (control-status bar)
- Where: a thin amber banner across the top whenever you do not have control
  (hidden once you have control or dismiss it).
- Controls: "Take Control" link (routes through Request Access if someone else
  holds it), "Cancel Request" link (while a request is pending, with a live countdown),
  and "X" to dismiss. Text states: "Agent 'X' is controlling this device" / "You are
  observing this device" / "Waiting for 'X' to respond (Ns)".
- Recovery relevance: explains why commands are blocked (you're an observer) and gives
  the one-click path to take control.

#### Notification Modal (forced-acknowledgement broadcast)
- Where: a full-screen blocking modal (blurred backdrop, no close button) when
  there are queued broadcast notifications.
- Controls: "I Acknowledge" (disabled until you scroll the body to the bottom; then
  advances the queue), a "Scroll to the bottom to continue" hint, and a "1 of N" badge for
  multiple queued notices.
- Recovery relevance: if you're "stuck" behind this modal, scroll to the end and click
  "I Acknowledge"; each acknowledgement reveals the next queued notice.

#### Console Log Panel (raw message drawer)
- Where: a drag-resizable drawer fixed to the bottom of the screen, collapsed to a
  thin title bar by default.
- Purpose: a live, low-level log of the raw messages exchanged between the dashboard
  and the kiosk — the operator's debugging window.
- Controls: drag the title bar to resize; Expand/Collapse chevron; "Clear"
  (trash) when expanded; the log shows Time, a "Device" (blue) / "Agent" (green)
  direction tag, and the raw message text (auto-scrolls to newest).
- Recovery relevance: the first place to look when a command "didn't work" — confirms
  whether the command was actually sent and what the device replied. An unread badge
  flags new device chatter while collapsed.

#### Task Reminder Popover
- Where: a small popover anchored beside the sidebar's "Tasks" item (desktop only);
  hidden on the Tasks page.
- Behavior: auto-appears every ~20 minutes when there are pending tasks and auto-hides
  after ~60 seconds. "View" (go to Tasks), "Dismiss" / "X". Shows the task count and
  "N overdue" (header turns red/orange when overdue).

---

### F. How buttons reach the kiosk

The agent's clicks are sent over a live connection to the selected kiosk, which performs
the action and reports status back. Commands only work when the device is online and the
agent has control; if you're observing, you'll see "You are in observer mode. Take control
of the device to send commands." Every action you send, and every reply the kiosk sends
back, also appears in the Console Log Panel so you can confirm a command actually went out
and see how the device responded.

---

<a id="part3"></a>

## Part 3 — Kiosk Features & Hardware Behavior

> This explains, in plain language, what physically happens on the kiosk when a front-desk
> agent uses each feature, what the hardware does, what statuses the agent sees, and how
> things recover when something goes wrong. Agents never type any of this — but knowing it
> lets a help chatbot answer questions like "what does Dispense actually do?" or "why did
> the scanner fail?".

---

### 1. How an agent's action reaches the kiosk

When an agent clicks a button on the dashboard, the action travels over a live connection
to the selected kiosk. The kiosk performs the action on its physical hardware and reports
the result back, which is what the agent sees on screen. Actions only work when the device
is "online" and the agent currently has control of it; if the device is offline or the
agent does not have control, the action cannot run.

The kiosk keeps trying to stay connected on its own. Whenever the connection drops it
reconnects automatically and announces itself as online again, re-syncs its settings, and
resumes normal operation. The dashboard's status indicators (online/offline, busy, hardware
ready or not ready, cash levels, errors) all come from these status reports the kiosk sends
back as things happen.

---

### 2. What each feature does

#### Cash dispenser / recycler

What the hardware does: this is a cash recycler that accepts banknotes, holds them briefly,
sorts them by denomination into internal storage, and can pay notes back out. It tracks how
many notes of each denomination are stored.

Normal success flow: the agent connects the cash device. Once it is ready, it loads its
denomination settings and reports its current contents and levels. For a cash-in, the
guest is shown an on-screen guide for where to insert the bill. As each note is inserted,
the kiosk accepts it, sorts it into storage, and updates the running total. When the
collected amount reaches the requested amount, it stops on its own. For a cash-out
(payout), the kiosk dispenses the requested amount note by note and reports when the payout
is complete. There is also a simple on-screen money display the agent can show the guest
(deposit, collected, amount due, refund) — this is just a display, not a hardware action.

What can go wrong and what the agent sees: messages such as "Cash device is not open" (it
needs to be connected first) or "Cash device already in transaction" (a cash-in or cash-out
is still running). A payout can fail for reasons that are shown in plain words, for example
the device does not have enough notes to make up the amount, it cannot pay the exact amount
requested, it is busy, or the input was invalid. If the device loses its connection
mid-transaction, the kiosk reports "Cash device disconnected" and safely closes out the
transaction. Suspected counterfeit notes are flagged rather than accepted.

How it recovers: the agent can reconnect the device, reset it, or do a full hardware reset.
An in-progress payout can be halted, and a note that is being held can be returned to the
guest. The denomination settings can be re-applied (the kiosk retries this several times if
the device reports it is busy). After a payout finishes or fails, and when the device goes
idle, the kiosk gives a short grace period and then safely closes the transaction.

#### Key / card dispenser

What the hardware does: this dispenses room-key cards out of a front slot, can pull a card
back in, can move a card to a reading position, and can move cards between an "issuing" box
(fresh cards to hand out) and a "recycle" box (returned cards).

Normal success flow: the agent connects the dispenser; it finds the device and reports
connected. Each card action (dispense a card to the front, capture a card back, recycle a
card, eject, and so on) runs and reports success, then re-checks the device's sensors. The
key card actions are also written to the session audit log so they show up in reports.

What can go wrong and what the agent sees: "No port configured" (the device has not been set
up in Settings), "Cannot find the key device" (it could not be located), or messages that
the device did not respond. The dispenser also reports the state of its internal sensors,
including whether the card box or recycle box is empty or full; if the sensors cannot be
read at all, it reports a sensor-query failure.

How it recovers: there are several reset and jam-recovery actions the agent can use to clear
a stuck card and return the mechanism to a normal state. The dispenser reconnects on its
own — if its connection was closed, the next action reopens it automatically. Front-slot
insertion can be allowed or blocked on demand.

#### ID scanner (passport / ID card)

What the hardware does: this is a document scanner. It initializes, takes a high-resolution
photo of the document placed on it, and uploads that image so the document details can be
read. Some scanner types also start themselves automatically when the kiosk boots and keep
reconnecting on their own if they drop.

Normal success flow: the agent initializes the scanner, which reports it is ready. Starting
a scan takes the snapshot and uploads it; the kiosk narrates progress to the agent
("Compressing image", "Uploading image") and reports when the scan is complete. On certain
setups it also reads the document details automatically and can pair a guest's two scanned
documents together.

What can go wrong and what the agent sees: "Scanner Disconnected", "Scanner Not Ready",
"Scanner Not Running", "Unable to take snapshot", or an upload failure message. The kiosk
reports the scanner's connected/disconnected state separately so the dashboard always knows
whether a scanner is present.

How it recovers: re-initialization is automatic — if the scanner is not ready when a scan
starts, it initializes first, and it stops cleanly after each capture. There is also a test
scan the agent can run with a sample image to confirm the whole upload path is working.

#### Indicator lights

What the hardware does: this drives the kiosk's status/indicator lights through a small
helper service that runs on the kiosk. The agent can turn individual lights on or off, turn
all of them on or off at once, and check which lights are currently lit.

Normal success flow: turning a light on or off succeeds immediately and the kiosk confirms
the new state. Asking for status returns which lights are currently on and which are off.

What can go wrong and what the agent sees: messages that the lights board is not initialized,
that the request was invalid, or that setting the lights failed; if the board is not present
the status comes back as "Disconnected". If the helper service cannot start, the kiosk gives
specific guidance (for example, that something required is missing on the machine, or that
another program is already using the port the service needs).

How it recovers: the lights controller is self-healing. Before each action it checks that the
helper service is healthy and reconnects if it is not. On startup it clears out any leftover
copies of the helper that were stuck holding the port, waits for the port to free up,
restarts the service, and waits for it to become ready. This is the fix for the old "did not
become ready" hang.

#### On-screen messages

What it does: the agent can show a message on the guest-facing screen — plain text (which is
automatically translated into the guest's language), a text-input prompt, a star-rating
prompt, a location pop-up, or an image slideshow. Each can be set to disappear after a chosen
amount of time.

Normal success flow: the message appears for the chosen duration. Guest actions come back to
the agent — for example the guest entered text, the message timed out, the guest dismissed
it, the guest went idle, or the guest picked a rating. Shown messages are also written to the
session audit log.

How it recovers: there is no hardware involved. A message clears when its timer runs out, when
the agent hides it, or when the guest interacts with it. If anything looks wrong, re-showing
the message simply redraws it.

#### Voice / speech

What it does: the agent can have the kiosk speak text aloud. The text is translated into the
chosen language, turned into speech, and played through the kiosk speakers.

Normal success flow: the audio plays through the speakers, and the spoken text and language
are written to the session audit log.

What can go wrong and what the agent sees: a speech error message if the speech service
cannot be reached or is not set up correctly. If the required credentials are missing, the
speech simply does not play and an error is shown.

How it recovers: there is nothing to reset — the agent re-issues the speech request once the
setup is corrected.

#### Camera / photo capture

What it does: the agent can capture a photo. If a video call is in progress, the kiosk grabs
a still image from the live call's video instead of the webcam (because the webcam is busy
during a call). Otherwise it uses the kiosk's physical webcam. The captured image is then
uploaded.

Normal success flow: the photo is taken and uploaded, and the kiosk reports the capture is
complete.

What can go wrong and what the agent sees: "Camera is unavailable — it may be in use by
another application" (commonly a video call), "Camera returned an empty frame", or a generic
capture error. These errors are also reported back so they show up for support.

How it recovers: during a video call the kiosk automatically uses the call's video for the
photo, which avoids the "camera in use" conflict entirely. Otherwise the agent should free
the camera (end the call or close other apps using it) and capture again.

#### Receipt printing

What it does: the agent can print a receipt. The receipt is built from a saved design (made
up of text lines, separators, spacing, label-and-value rows, QR codes, images, and barcodes,
with the guest's and stay's details filled in) and sent to the selected or default printer.
There is also a simpler fixed receipt format (hotel name, contact, room number, Wi-Fi,
checkout and breakfast times, and footer notes), a way to list the available printers, and a
way to open the receipt designer.

Normal success flow: the receipt prints, the kiosk reports success, and the print is written
to the session audit log (printer name, paper type, and the details used). Listing printers
returns the available printer names and which one is the default.

What can go wrong and what the agent sees: a print failure (the printer rejected the job) or
a print error message. If the requested printer is not installed, the kiosk quietly falls
back to the default printer. Remote images that cannot be loaded are simply skipped.

How it recovers: the automatic fallback to the default printer covers a misnamed printer; the
agent can list printers to find a valid name. There is no automatic retry — the agent simply
prints again.

#### Video call

What it does: the agent can start a video call with the guest on the kiosk. The kiosk opens a
dedicated, fresh video window, joins the call, and connects audio recording. During the call,
some on-screen features (such as the hotel-name banner, fill-screen, and captions) can be
forced on and revert by themselves after about a minute if turned off. The agent can also
start and stop recording the conversation.

Normal success flow: the agent sees the call progress through "joining", then "waiting" (in
the lobby), then "joined". Once joined, the on-screen features (banner, fill-screen, captions)
are applied and recording can run. Motion detection runs quietly during the call.

What can go wrong and what the agent sees: an error if the call details are invalid or a call
is already starting; "Join request denied" or being removed from the call, which triggers an
automatic retry; or the message that the video window crashed and is recovering.

How it recovers: the agent can refresh the call, which closes and relaunches it. If the kiosk
is repeatedly denied or removed from the call, it rebuilds the call with a clean profile,
waiting a little longer between attempts each time. If the video window crashes, the kiosk
relaunches it automatically and restarts recording if it was running. The agent can also
clear the call's stored browsing data if needed.

#### Motion detection (during a video call)

Motion detection runs automatically during a video call — there is no separate switch for the
agent. It watches the call's video and flags when meaningful movement is seen, which is used
to confirm that someone is actually present and active on the call. It resets itself at the
start of each new call.

---

### 3. How the kiosk reports its status (where the dashboard indicators come from)

The dashboard's indicators are built from the status the kiosk reports as events happen,
rather than from a constant heartbeat. In plain terms:

- Online / offline: the kiosk announces itself as "online" when it connects and "offline"
  when it shuts down. The online/offline dot on the dashboard comes from this plus whether
  the live connection is currently up.
- App version: the kiosk reports its installed version when it connects, so the dashboard
  always shows the current version of the device.
- License health: the kiosk periodically confirms its license is still valid. If the license
  is invalidated, the kiosk clears the license and restarts.
- "Screen blocked" alert: the kiosk watches whether another window is covering its screen and
  raises a Kiosk Alert when it is covered (and tries to bring itself back to the front). This
  drives the alert banner the agent sees.
- Cash device state and levels: the kiosk reports the cash device's contents and per-storage
  note counts when it connects, after each note, after any settings change, and on demand.
  Live note movement and cash-box additions are reported as they happen, so the dashboard's
  cash levels stay current.
- Key dispenser status: the kiosk reports connected or disconnected, and the state of its
  card box and recycle box (including empty or full) after each successful card action.
- Scanner status: the kiosk reports whether a scanner is connected and when a scan completes.
- Indicator lights: the kiosk reports which lights are on, confirms each light change, and
  reports "Disconnected" if the board is not present.
- Video call state: the kiosk reports the call moving through joining, waiting, joined,
  retrying, recovering after a crash, and ended.
- Session audit events: receipts printed, messages shown, speech played, and key card actions
  are recorded against the device's current session, which is what appears in the Transaction
  Reports and Session Command Events pages.
- General activity log: most actions narrate their progress and any errors back to the
  dashboard, which shows them in the console log panel for the agent.

There is no constant hardware heartbeat beyond the periodic license check and the screen-cover
check. Device health is reported as things happen — on connect, on a state change, and after
each action.

---

### 4. Recovery behaviors at a glance (kiosk side)

- Connection: the kiosk reconnects to the backend automatically and keeps retrying
  indefinitely. On reconnect it re-announces itself, re-syncs its settings, and reports any
  scanner startup error.
- Cash dispenser: the agent can reconnect, reset, or hardware-reset the device, halt a payout
  in progress, return a held note, and re-apply the denomination settings (retried if the
  device is busy). Transactions close out automatically after a payout finishes or fails and
  when the device goes idle, and a lost connection is closed out safely with a "Cash device
  disconnected" report.
- Key dispenser: it reconnects on its own when needed, and there are reset and jam-recovery
  actions to clear a stuck card and return the mechanism to normal.
- ID scanner: it re-initializes by itself if it is not ready when a scan starts, stops cleanly
  after each scan, and offers a test scan to confirm the upload path. Self-starting scanners
  re-initialize shortly after boot and on reconnect.
- Indicator lights: self-healing — the kiosk checks the lights service before each action and
  reconnects if it is unhealthy, and on startup it clears out any leftover stuck copies,
  frees the port, and restarts the service, with specific guidance if the port is held or
  something required is missing.
- Video call: it rebuilds with a clean profile if it is repeatedly denied or removed (waiting
  longer between attempts each time), relaunches automatically if the video window crashes
  (and restarts recording if it was running), can be refreshed manually, and can have its
  stored data cleared. When recording stops, the kiosk holds on briefly so trailing audio is
  not lost.
- Camera: if the webcam is busy (commonly during a video call), the kiosk transparently grabs
  the photo from the call's video instead.
- App level: an update closes the app and installs the new version; an invalidated license
  clears the license and restarts; and if another window covers the kiosk, it brings itself
  back to the front.

---

<a id="part4"></a>

## Part 4 — Troubleshooting & Recovery

> Symptom-first guide for the help chatbot, scoped to the agent experience. Each entry is
> Symptom, then Likely cause, then What to do. Start with the universal flow; then jump to
> the matching feature.

---

### 0. Universal first checks (covers ~80% of "it's not working")

Walk these in order before anything feature-specific:

1. Is the device Online? Check the "Device" badge in the top bar (green = online). If
   red/offline, commands won't reach the kiosk — wait for it to reconnect (the kiosk
   auto-reconnects every couple of seconds) or have someone check the physical kiosk.
2. Do you have control? If the badge shows "Observing" (amber) or the Observer Banner is
   showing, your command buttons are blocked. Click "Take Control" (if free) or "Request
   Access" (if another agent holds it).
3. Refresh the page. This re-syncs device presence and control state and clears most
   "stuck" UI. It is the single most effective recovery action.
4. Is a transaction required? Guest-facing pages (Scanner, Cash, Key, Print, Ratings,
   Photo, Guest Details, Document Signature) need an active transaction. If you were
   redirected to the dashboard home, press "Start Transaction" first.
5. Check the Console Log Panel (bottom drawer) — confirm your command actually went out
   (green "agent" line) and what the device replied (blue "device" line).
6. Switch or re-select the device (top-bar "Switch Device") if control or session state
   looks wrong.
7. Re-login if you were bounced to the login screen (your access expired or was revoked).

---

### 1. Connectivity & status

Backend badge is red / whole dashboard not updating.
Your dashboard lost its live connection to the server. It reconnects automatically. If it
persists: refresh the page; check your internet; if a toast said "token revoked" or
"account deactivated" you'll be sent to login — sign in again.

Device badge is red (kiosk offline).
The kiosk isn't connected. Nothing you send will arrive. The kiosk auto-reconnects
indefinitely (a couple of seconds' delay). If it stays offline, the physical kiosk may be
powered off, mid-update, or off the network. Status refreshes via live presence updates and
a re-check every 30 seconds.

Status looks stuck / wrong (e.g. shows offline but you know it's up).
Refresh the page — this re-requests the device list and re-syncs presence. The page also
re-syncs automatically when you switch back to the browser tab.

"Kiosk screen blocked" red banner across the top.
The kiosk reports its screen is covered by another window, so the guest can't see it. Bring
the kiosk app back to the foreground (the kiosk also tries to re-foreground itself) or
escalate to someone on-site.

---

### 2. Device control / observer mode

My buttons are greyed out / "You are in observer mode. Take control of the device to send
commands."
Another agent controls the device (or it's free and you haven't taken it). Use "Take
Control" (free) or "Request Access" (held by someone) from the top bar, the Observer Banner,
the sidebar Observer-Mode footer, or the Quick Actions panel.

My control request got no response / was denied.
Requests auto-expire after about 30 seconds. Toast outcomes: denied; timeout ("no response,
you can request again"); busy ("another request is already pending"); or superseded ("device
control was changed"). You can request again.

I lost control unexpectedly.
Either another agent was approved for control (you'll see a toast and drop to observer), or
control was reassigned some other way. Request access again to resume.

---

### 3. Transaction session

A guest-facing page keeps bouncing me to the dashboard home.
That page is transaction-gated and there's no active session. Press "Start Transaction" in
the top bar first.

"Transaction session timed out."
Sessions auto-end after the configured timeout (default 30 minutes). Start a new transaction
to continue.

"Active session exists" conflict dialog when I press Start Transaction.
A session is already running on this device (possibly started by another agent). Choose
"Connect to existing session" (reattach) or "Close & start new" (end it and start fresh), or
"Dismiss".

The transaction ended by itself right after the key dispensed.
That's expected — a successful key-card dispense auto-completes the transaction
("Transaction completed — key dispensed").

"Missing guest details" dialog after a session ends.
Required fields (name, room no, account no, room amount, deposit amount) are missing. Fill
them so the transaction record is complete.

---

### 4. Cash dispenser / recycler

The Cash Dispenser page has a dedicated "Recovery & Diagnostics" panel — an escalation
ladder from safest to most drastic. Use it in this order:

1. "Clear Transaction" — fixes a UI that thinks a transaction is active when the device is
   actually fine; clears host-side state and disables the acceptor/payout.
2. "Refresh" — re-pulls device info and recycler counts (disabled when offline).
3. "Return Escrow" — returns a banknote stuck in the bezel/escrow. Only enabled when a note
   is actually held.
4. "Halt Payout" — aborts an in-progress dispense. Only during an active cash-out.
5. "Reset Device" — soft firmware reboot; cancels active transactions (confirmation dialog).
   Use for error/jam states.
6. "Reload Routes" — re-applies saved denomination routes (disabled during an active
   transaction).
7. "Device COM RE-Attempt" — closes and reopens the device connection; last resort for lost
   communication (confirmation dialog).

Common symptoms:
- "Cash device disconnected" / recycler & cashbox values cleared. The device lost its
  connection; most buttons disable until it reconnects (it restores them once it
  reconnects). Try "Device COM RE-Attempt"; check the physical cable/power.
- A dispense/payout failed (red toast). The reason is shown as a message: not enough value
  (recyclers don't hold enough to make the amount), cannot pay exact amount (no denomination
  combination fits), device busy, not supported, and similar. Refill/adjust routes or
  dispense a payable amount.
- A note is stuck in the bezel. Use "Return Escrow". Note that "Reset Device" and "Device
  COM RE-Attempt" cancel active transactions and an escrowed bill may need manual return.
- Recycler totals look wrong. If a recycler's denomination was changed while it still held
  old notes, totals can be inaccurate (the info tooltip warns about this) — empty and
  reconfigure routes.
- Buttons disabled mid-dispense. Intentional, to prevent overlapping payouts. Wait for the
  current dispense to finish.
- Cash-in won't start. Start Cash-In is disabled if the device is disconnected, there's no
  session, a payout is in progress, the guest name is empty, or room amount isn't greater
  than zero.

---

### 5. Key / card dispenser

The dispenser jammed or faulted.
Use the "Recovery" buttons on the Key Dispenser page, in roughly this order: "Reset Device"
(full reset, moves any card to recycle), then "Reset (Keep Card)", then "Reset → Issuing
Box" (return card to hopper), then "Reset → Recycle Box".

All key buttons are disabled.
The device is disconnected. Press "Connect" — the page also auto-connects when opened, and
the kiosk probes all device addresses to find it. The connection also auto-reconnects on the
next command if it dropped.

Status badges show "Card Box: Empty/Low" or "Recycle: Full".
The hopper needs refilling or the recycle box needs emptying (physical action on the kiosk).
"Channel: Jam/Overlap/Card Present" indicates a transport jam — run a Reset.

A card is stuck.
"Eject from Bayonet" pushes a held card out; "Capture / Recycle" pulls it into the recycle
box; or use the resets above.

Errors appear as red error lines in the Event Log.
Read the message. "Sensor query failed" means the status read failed — reconnect and refresh
status.

---

### 6. ID scanner

Start Scan is disabled.
A scan is already active, there's no active transaction, or no guest name is on file. Fill
the guest's full name first (the page shows a blocking "Guest Full Name Required" overlay
when missing).

A scan is stuck / spinning.
Press "Cancel Scan". Leaving the page while a scan is active also auto-cancels. The scanner
auto-re-initializes on the next "Start Scan" if it wasn't ready.

The scan returned no data.
The details dialog will say the document may be unreadable or the reading service
unavailable. Re-scan with a cleaner placement. For two-sided IDs the page prompts to flip
and scan the second side automatically.

"Scanner Disconnected" / "Status Unknown" badge.
The scanner lost connection; reconnect the hardware. A built-in test scan validates the full
capture-and-upload path.

Compliance alerts (DNR, name mismatch, under-age).
These are expected workflow prompts, not errors — acknowledge the DNR or name-mismatch
dialog, and review the age badges ("Age Below 18" red / "Age Below 21" amber).

---

### 7. Photo capture

Capture failed (red toast + error row).
Just capture again. If the webcam is busy (commonly because a video call is active), the
kiosk automatically grabs the frame from the call video instead — so during a call, capture
still works. "No device connected" means the kiosk is offline.

---

### 8. Receipt printing

"No active receipt design found for this device."
Create and activate a design under "Receipts" (Receipt Designer) — the kiosk prints the
active design.

The printer dropdown is empty.
You're not "In Control", the list is still loading, or the kiosk returned none. Take control
and click "Refresh Printer Options". In all those cases printing still falls back to the
kiosk's default printer.

Print failed (failed / error toast).
The printer rejected the job or errored. If you named a printer that isn't installed, the
kiosk silently falls back to the default. Check the printer is on/loaded and re-send.

Print Receipt button is disabled.
A required (non-kiosk-time) variable is still empty — fill all required fields. Kiosk-time
variables are intentionally disabled ("Kiosk system time will be used").

---

### 9. Video call

"Join request denied."
The host didn't admit the kiosk. Click "Retry Call" (force-starts a fresh attempt).

"Active Session Detected" conflict card.
A call is already running. Use "End Previous & Start New" (force-start) or "Cancel".

The video status shows it crashed and is recovering.
The kiosk's video window crashed; it recovers on its own (it relaunches automatically).
Wait; if it doesn't recover, end and restart the call, or refresh the call from the kiosk.

"Removed from call" right after connecting.
A 10-second reconnect grace ignores spurious removals just after (re)connecting. If it's
real, the kiosk auto-retries with a fresh profile; otherwise Retry or End and restart.

"Invalid video call URL or code."
The link/code is malformed. Paste a valid video call link or code.

A kiosk display toggle won't stay off.
Some toggles (Hide Call Controls, Show Hotel Name, Fill Screen, and sometimes Captions) may
be enforced for the call and auto-revert about 60 seconds after being switched off (while
you're in control). This is a per-device configuration.

Guest is requesting assistance (sound + browser notification).
The guest tapped for help; enable the video display and respond.

---

### 10. Indicator lights

Lights page shows "Disconnected" and all controls are disabled.
The light controller (IO board) isn't reachable. Press "Refresh" — the kiosk's helper
self-heals (health-checks and reconnects, and on startup clears any leftover helper
processes). If it stays disconnected, the board, its USB connection, or the light-controller
helper on the kiosk needs attention.

"Indicator lights are disabled for this device."
The device's Indicator Lights option is set to "None". Enable it in Settings (choose the
light-controller option).

Channel names show generic "Channel 1…12".
The label mapping for this fleet isn't configured. Ask a fleet manager to set channel labels.

---

### 11. On-screen content stuck (message / animation / slideshow / voice)

A message/animation/slideshow is stuck on the kiosk screen.
Use the matching Hide control: "Hide Message", "Hide Animation", "Stop" (slideshow), or
"Hide Input". Quick Actions has Hide buttons for all of these.

Text won't send / over the limit.
Messages and voice text are capped at 250 characters. Trim and resend.

Guest replies aren't being saved.
There's no active transaction — guest message input is only saved during a session (an amber
warning appears, and unsaved replies are flagged). Start a transaction first.

Voice (text-to-speech) didn't play.
The kiosk requires text-to-speech credentials; if missing it fails silently with a
text-to-speech error message. Otherwise confirm the kiosk speakers/volume and that the
device is online.

---

### 12. Legal documents / signature

Send to Kiosk is disabled.
No template selected, no active transaction, or you lack the Send-to-Kiosk permission. Pick a
template, start a transaction, or ask your administrator to grant the permission.

No templates appear in the dropdown.
Only templates that have at least one field can be sent. Create fields in the Field Editor
(and upload the source document in File Storage first).

The document errored / the guest cancelled.
The kiosk reports an error or cancellation; the open-document panel closes and the
submissions list refreshes — resend if needed. Watch the "Kiosk:" line for live status.

Document won't load in the Field Editor ("Failed to load PDF").
The underlying file may have been removed from File Storage — confirm it still exists.

---

### 13. Notifications modal won't close

A full-screen notification is blocking the screen with no close button.
This is a forced-acknowledgement broadcast notification. Scroll the body to the very bottom,
then click "I Acknowledge". Each acknowledgement reveals the next queued notice. (It can't be
dismissed with Esc or by clicking outside.)

---

### 14. Login & access (agents)

Login phase 1 keeps me on "Waiting for authorization…".
Your browser or network is new and needs approval. It resolves automatically once that
approval happens.

"Account Locked" with an unlock time.
Too many failed logins. Wait until the stated unlock time, or ask your administrator to
unlock the account.

"Account Deactivated."
Your account was disabled. Ask your administrator to re-activate it.

"Location Blocked" (geo-blocked).
You're outside the allowed area. You must sign in from an allowed location.

"Too many failed attempts. Please wait 10 minutes…" (rate-limited).
Wait about 10 minutes and retry.

I logged in but can't reach a device / "No devices assigned."
On the device-selection screen you can only pick devices you're assigned to. Ask your
administrator to add an assignment. Selection can also fail with: "locked by an
administrator"; "no longer assigned"; or "no longer exists". Use "Retry" to re-load your
device list (it also re-checks every few seconds).

Switching device / something is off — start clean.
Use the top-bar "Switch Device" button (or the device-selection screen) to drop and
re-acquire the device.

---

### 15. Reports & data

A report looks stale.
Transaction reports are never cached (always refetched). Change a filter or revisit the page.

Export failed.
Retry the "Export XLSX"; confirm a device and filters are selected. Exports respect the date
filters but cover the whole filtered set (not just the current page).

A session is stuck "ongoing" long after the guest left.
The session never closed cleanly on the kiosk (missing End Time). Open the session to inspect
its events. It will also auto-close at the configured timeout.

Red "fraud attempt" cash event types.
These flag rejected or suspect notes — not a UI error; review the session.

---

### Quick reference: which recovery control lives where

| Problem area | Where to recover |
|--------------|------------------|
| Lost control / observer | Top bar "Take Control / Request Access"; Observer Banner; sidebar footer |
| Cash hardware | Cash Dispenser, then "Recovery & Diagnostics" panel (Clear Transaction, then Refresh, then Return Escrow/Halt, then Reset Device, then Reload Routes, then Device COM RE-Attempt) |
| Key dispenser | Key Dispenser, then "Recovery" resets; "Connect" if disconnected |
| Scanner | ID Scanner, then "Cancel Scan"; re-Start (auto re-init) |
| Printing | Print, then take control and "Refresh Printer Options"; activate a design under Receipts |
| Video call | Video Call, then "Retry Call" / "End Previous & Start New"; auto-recovers on crash |
| Lights | Indicator Lights, then "Refresh"; enable in Settings |
| Stuck on-screen content | Quick Actions / page "Hide" buttons |
| Notification modal | Scroll to bottom, then "I Acknowledge" |
| Account locked / deactivated / no devices | Contact your administrator |

---

<a id="part5"></a>

## Part 5 — Hardware Guide & Device Configuration

> A plain-language reference for the physical hardware inside a Kiotel kiosk and the
> configuration fields on the agent-side Settings page. Written for front-desk agents,
> and the help chatbot. It does not cover fleet-wide administration.

---

### 1. Cash dispenser / recycler

#### What it is
This is the machine that accepts cash from guests and, on supported models, can also pay cash
back out. Some units only accept notes; the "recycler" type can both accept notes and reuse
those same notes to make change later. The kiosk recognizes the connected unit automatically.

These are Innovative Technology (ITL) cash machines. In Settings, the cash type can be chosen
as "NV4000" or "NV200" depending on the model installed. Pay-out and change-making only work
on recycler-capable units; an accept-only validator can take cash but cannot pay any out.

#### What the events mean (seen in reports)
When cash moves through the machine, these words appear in the event log and Transaction
Reports:

- "Escrow / held" — a note has been read and is being held while the system decides to keep or
  return it.
- "Accepted / Stacked" — the note was kept and dropped into the secure cashbox (it will not be
  paid back out).
- "Stored" — the note was kept in the recycler so it can be used later to make change.
- "Dispensing" — notes are currently being paid out to the guest.
- "Dispensed" — a note was successfully delivered to the guest.
- "Returned" — a note was handed back to the guest instead of being kept.
- "Fraud attempt" — the machine flagged a suspected fake or tampered note while handling it.

#### Status / "State" shown on the recovery panel
The machine reports its current state in plain words such as: not connected, connecting,
starting up, ready/idle, accepting cash, paying out, emptying, refilling, recovering from a
jam, or error. A few are worth knowing:

- When it finishes starting up, it reloads its settings and refreshes its on-screen totals.
- If it goes into "error", the current transaction is closed safely and the problem is
  reported.
- If it is disabled, it waits a few seconds and then closes the transaction.
- If it disconnects, the transaction is closed and the dashboard is told the device went
  offline.

#### Device problems (what "the cash machine errored" usually means)
When the cash machine shows an error, it is almost always one of these:

- "Jam" — a note is stuck in the note path or in the stacker.
- "Stacker full" — the secure cashbox is full and must be emptied.
- "Cashbox removed" — the cashbox (or a refill cassette) has been taken out and needs to be
  put back.
- "Disconnected" — the kiosk lost its connection to the machine.

#### Why a pay-out can fail (in plain English)
If the kiosk tries to pay cash and can't, the reason is one of:

- "The device can't pay out" — this unit is accept-only and has no pay-out ability.
- "Not enough notes stored to pay that amount" — there is less stored cash than the amount
  requested.
- "Can't make the exact amount" — the stored notes can't be combined to total the exact amount
  needed.
- "Device busy" — the machine is in the middle of something and can't pay out right now.
- A bad request — the pay-out details could not be understood.

The machine also only handles one currency. If it is loaded with mixed currencies, pay-outs
and change-making won't work.

#### Fullness and limits
Fullness is shown as states rather than exact counts. You will see indicators like
"full / requires emptying" rather than a precise number of notes. The machine does report live
note counts per store, but for emptying decisions the simple "full" state is what matters. A
new cash-in or cash-out is refused while another cash transaction is still in progress.

---

### 2. Key / card dispenser

#### What it is
This is the unit that issues room keycards to guests and can pull used cards back in. It moves
a card to a read/write position, hands a card out the front slot, pulls a card into a recycle
box, and can open or close the front slot to accept an inserted card. The unit is a K720-type
card dispenser.

#### Status badges and what they mean
The dispenser reports four simple statuses — the overall device, the card transport path, the
issuing card box, and the recycle box:

- "Idle / OK" — the dispenser is healthy and ready.
- "Fault" — the device has a problem and needs attention.
- "Jam" — a card is stuck in the transport path; clear it before continuing.
- "Card present" — there is a card sitting in the transport path.
- "Card Box: Empty" — there are no blank cards left to issue; refill the cards.
- "Card Box: Low" — the blank-card supply is running low; refill soon.
- "Card Box: Full" — the issuing card box is full.
- "Recycle Box: Full" — the box of captured/returned cards is full; empty it.

If the status can't be read at all, it usually means the device is not connected.

#### Recovery
If the dispenser stops responding, the kiosk re-opens the connection automatically on the next
action. For "Card Box: Empty / Low" refill the blank cards; for "Recycle Box: Full" empty the
captured cards; for "Jam" clear the stuck card from the path.

---

### 3. ID / passport scanner

#### What it is
This is the flatbed reader that takes a high-resolution photo of a guest's ID or passport. It
lights the document and captures a clear, full-color image, which is then sent for processing.

#### Scanner and OCR choices in Settings
There are different scanner and text-reading setups, chosen in Settings:

- Scanner choice: the standard local reader (a Sinosecu document reader) or the older reader
  (the exact option is set in Settings under "Scanner Option").
- Text-reading (OCR) choice: "InHouse" (the kiosk reads the text itself), "InHouse Cloud" (the
  back office reads the text), or "GuestBan" (a screening service reads the text and also
  checks for risk).

#### What the scanner captures and what it decides
The scanner's job is to capture a high-resolution photo of the document. It does not decide
what the document is or whether the guest is allowed to rent. The document type (passport,
driver license, visa, ID card, and so on) and any compliance alerts — such as age checks,
do-not-rent / ban flags, name mismatches, and risk scores — are all determined by the system,
not on the kiosk itself. When the "GuestBan" option is used, the ban and risk alerts come from
that screening service.

If a document has two sides, the system handles the front and back automatically: after the
first side is captured, the next capture is treated as the second side.

---

### 4. Indicator lights

#### What it is
This is an indicator-light board with 12 separate light channels, numbered 1 through 12. A
small helper program runs the board on the kiosk's behalf. In Settings the light board type is
chosen as "U10" or "None" (none meaning no light board installed).

#### How it works for users
Each light channel can be turned on or off. The names for each channel (what each light means)
are configured centrally, not on the kiosk. The helper program that runs the board looks after
itself: if it stops responding or a leftover copy is in the way, it cleans up and restarts
automatically, then continues once it is ready again.

---

### 5. Receipt printer

#### What it is
This is a thermal receipt printer (the kind that prints on heat-sensitive paper, no ink).
Typical models are the Cashino EP-380CK and KP-300H.

#### Paper and what it can print
- It supports two paper widths: 80mm (wider) and 58mm (narrower). The chosen width controls how
  wide lines and columns are laid out.
- A receipt can include text (with alignment, larger or bold text), dividing lines, blank
  spacing, key-and-value rows (a label on the left and a value on the right), QR codes,
  barcodes, and images such as a hotel logo.
- Receipts print to a chosen printer if it is installed, or to the computer's default printer
  otherwise.

---

### 6. Camera

#### What it is
This is the camera that takes a photo of the guest.

#### How it captures
- When there is no video call in progress, it takes the photo from the kiosk's webcam.
- During a video call, the webcam is being used by the call, so instead the kiosk captures the
  guest's photo from the call's own video. This way a guest photo can still be taken even while
  the webcam is busy.

#### Errors
If a photo can't be taken, the message will say the camera is unavailable (it may be in use by
another application, such as the video call) or that it returned an empty image. Guest photos
are saved as standard image files.

---

### 7. Motion detection (during video calls)

#### What it is
This is a feature that watches for movement during a video call.

#### How it works for users
- It runs only while a video call is in progress.
- It watches the call's video for movement.
- It is completely invisible to the guest — nothing about it appears on the guest's screen.
- It only watches once there is live video to look at; if the call's camera is off, it stays
  paused until video appears.
- There is currently no dedicated dashboard control for this feature.

---

### 8. Where dashboard status indicators come from

The badges, levels, and logs you see on the dashboard — online / offline, connected or not,
cash levels and cash events, the scanner connected status, key dispenser status, light status,
and the activity logs — are all fed by the kiosk reporting its own status continuously. The
kiosk sends up what each device is doing as it happens, and the dashboard simply displays that
live information.

---

### 9. Device Settings (what each field on the agent Settings page does)

The agent Settings page (/dashboard/settings) is grouped into sections. Below is what each
field does, in plain terms.

#### 9.1 Hotel & contact information
- "Hotel Name" — the hotel name shown to guests. It also appears live on screen during a
  video call as the hotel-name banner.
- "Support Email" / "Phone" — the support contact shown to guests if they need help.
- "Check Out Time" / "Breakfast Time" — the times displayed to guests on screen.
- "Body Notes" / "Footer Notes" — free-text messages shown to guests on screen and on receipts.

#### 9.2 WiFi
- "WiFi Name" — the guest WiFi network name shown on screen.
- "WiFi Password" — the guest WiFi password shown on screen.

#### 9.3 Hardware ports
- "Cash Port" — which port the cash machine is connected to.
- "Key Port" — which port the key dispenser is connected to.
- "Baud Rate" — the connection speed for the key dispenser (the cash machine manages its own
  connection speed and does not use this).

#### 9.4 Peripheral choices
- "Scanner Option" — which ID scanner this kiosk uses. Pick the model that matches the
  scanner physically connected to the machine.
- "Cash Dispenser Type" — which cash machine model this kiosk uses. "NV4000" is the
  4-recycler model (set four bill denominations, Recycler 1–4); "NV200" is the payout-store
  model (up to seven payout denominations; matching bills are kept for change and the rest
  go to the cashbox).
- "OCR Option" — which document-reading service is used to read scanned IDs. Choose from the
  options offered in the dropdown. If left blank, the system uses its default. "GuestBan" is
  disabled with "(key not configured)" until that integration is set up centrally.
- "Indicator Lights" — choose "U10" if the kiosk has the indicator-light bar attached, or
  "None" if it does not. Choosing "None" turns off the Lights page for that kiosk.

#### 9.5 Cash denomination routes & cashbox
How cash is sorted depends on the "Cash Dispenser Type" you chose:
- For the 4-recycler model: "Recycler 1–4 denominations" — the bill value loaded into each
  of the four storage cassettes. These are required.
- For the other model: up to seven payout denominations and the currency. Bills that match a
  payout denomination are kept for giving change; every other bill goes to the cashbox.
- Cashbox Status: Cashbox Capacity, Note Count, Total Amount, and a "Reset Cashbox to Zero"
  action are also managed from Settings.

#### 9.6 Simulation Mode
"Simulation Mode" lets you run and test a kiosk without any real hardware attached. An agent
can toggle "Simulation Mode" on the Settings page if they have the simulation permission.
When it is on, every device is replaced with a simulated version (cash machine, key
dispenser, light bar, and the matching simulated ID scanner), and a "Simulation Panel" opens
— a small always-on-top control window for driving the fake hardware. Everything else
behaves normally; only the physical devices are faked.

What you can do from the Simulation Panel:
- Cash machine — connect or disconnect; watch live transaction and storage status; press
  buttons to "insert" $1, $5, $10, $20, $50, or $100 bills during a cash-in; accept or reject
  a bill being held; and dispense bills with a progress indicator.
- Key dispenser — see whether it is connected and the card-box status; set how many cards are
  loaded; and simulate a jam or clear an alert.
- ID scanner — see whether it is ready and what it is doing; optionally override the scanned
  date of birth so you can test age checks; for image-based scanners, pick an image file and
  send it; for others, complete or fail a scan on demand.

---

### 10. Startup, updates & approval (what an agent may see)

- The kiosk is tied to the specific physical machine it runs on and must be approved before
  it can operate. If the machine's hardware changes significantly, or access is revoked, the
  kiosk will show a "Pending Approval" or login screen until it's re-approved — this is not
  something an agent can fix locally.
- Software updates are pushed centrally: when an update runs, the kiosk closes itself,
  reinstalls the new version, and reopens. Some updates also reinstall the document-reading
  (OCR) components as part of the same update.
- Startup sequence (what the splash screen is doing): the kiosk loads its settings, confirms
  it's an approved device, validates required configuration (see section 9), prepares
  document-reading and motion-detection components, warms up the ID reader, then shows the
  main kiosk screen and connects to the dashboard. If a required Settings field is blank, it
  shows a "Configuration Error" and returns to login — an agent should check Settings for
  missing required fields in that case.
- Changing a setting from the agent Settings page applies right away and only re-prepares the
  hardware affected by that change (e.g. changing "Scanner Option" re-prepares just the
  scanner). Changing "Simulation Mode", "Hotel Name"-type fields, or display toggles takes
  effect without re-preparing any hardware. While in Simulation Mode, hardware is never
  re-prepared.

---

### See also
- Part 2, section D ("Settings (device configuration)") — the agent-facing Settings page UI.
- Part 3 — what each kiosk feature does physically when triggered from the dashboard.