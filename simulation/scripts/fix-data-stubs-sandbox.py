#!/usr/bin/env python3
"""Añade stubs mínimos en lovable/data/* para que build:devaws pase tras empalme."""
from __future__ import annotations

import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "sandbox" / "DoEventsWEB" / "packages" / "shell" / "src" / "lovable" / "data"

PATCHES: dict[str, str] = {
    "mockData.ts": """
export const mockPosts: import('@doevents/shared').FeedUiPost[] = [];
export const myFollowers: import('@doevents/shared').FeedUiUser[] = [];
""",
    "salesStatsData.ts": """
import type { EventChatRoom } from './chatData';

export const generateMockSalesData = (event: EventChatRoom): EventSalesData => ({
  eventId: event.id,
  eventName: event.eventName,
  venueName: '',
  currency: 'COP',
  categories: [],
});
""",
    "refundsData.ts": """
import type { EventChatRoom } from './chatData';

export const generateMockRefundsData = (
  event: EventChatRoom,
  policyType: RefundPolicyType = 'days_1',
): EventRefundsData => ({
  eventId: event.id,
  eventName: event.eventName,
  currency: 'COP',
  policyLabel: '',
  policyLimitDays: 0,
  policyType,
  requests: [],
});
""",
    "chatData.ts": """
export const mockPrivateChats: PrivateChat[] = [];
export const mockChatRooms: EventChatRoom[] = [];
""",
    "invitationsData.ts": """
export const mockInvitations: InvitationEvent[] = [];
""",
    "venuesData.ts": """
export const MOCK_VENUES: Venue[] = [];
""",
    "eventFormData.ts": """
export const mockCompleteEvent: EventFormData = initialEventFormData;
""",
}

TICKETS_STUB = """
import { useSyncExternalStore } from 'react';

let tickets: Ticket[] = [];
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const getTickets = () => tickets;

export const addTickets = (newTickets: Ticket[]) => {
  tickets = [...newTickets, ...tickets];
  emit();
};

export const useTickets = () =>
  useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => tickets,
    () => tickets,
  );
"""


def ensure_snippet(path: Path, snippet: str, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    path.write_text(text.rstrip() + "\n" + snippet.strip() + "\n", encoding="utf-8")
    return True


def main() -> int:
    changed = []
    for name, snippet in PATCHES.items():
        path = DATA / name
        if not path.exists():
            continue
        marker = snippet.strip().split("\n")[-1].split("=")[0].strip().split("(")[0].replace("export const ", "").replace("export ", "")
        if ensure_snippet(path, snippet, marker):
            changed.append(name)

    tickets = DATA / "ticketsData.ts"
    if tickets.exists() and "useTickets" not in tickets.read_text(encoding="utf-8"):
        ensure_snippet(tickets, TICKETS_STUB, "useTickets")
        changed.append("ticketsData.ts")

    admin_bridge = Path(__file__).resolve().parents[1] / "sandbox" / "DoEventsWEB" / "packages" / "shell" / "src" / "lovable" / "components" / "admin" / "AdminPanelView.tsx"
    prod = Path(__file__).resolve().parents[3] / "DoEventsWEB" / "packages" / "shell" / "src" / "lovable" / "components" / "admin" / "AdminPanelView.tsx"
    if prod.exists() and admin_bridge.exists():
        prod_text = prod.read_text(encoding="utf-8")
        if "AdminPanelPage" in prod_text and "AdminPanelPage" not in admin_bridge.read_text(encoding="utf-8"):
            admin_bridge.write_text(prod_text, encoding="utf-8")
            changed.append("AdminPanelView.tsx (bridge)")

    print(f"patched {len(changed)} files")
    for c in changed:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
