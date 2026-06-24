#!/usr/bin/env python3
"""Stubs mínimos en lovable/data/* para build:devaws tras empalme (WEB productivo o sandbox)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reutiliza lógica del script de simulación
SIM_SCRIPT = Path(__file__).resolve().parents[2] / "simulation" / "scripts" / "fix-data-stubs-sandbox.py"


def patch_web(web_root: Path) -> list[str]:
    data = web_root / "packages" / "shell" / "src" / "lovable" / "data"
    if not data.is_dir():
        return []

    patches: dict[str, str] = {
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

    tickets_stub = """
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

    changed: list[str] = []

    def ensure_snippet(path: Path, snippet: str, marker: str) -> None:
        nonlocal changed
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        if marker in text:
            return
        path.write_text(text.rstrip() + "\n" + snippet.strip() + "\n", encoding="utf-8")
        changed.append(path.name)

    for name, snippet in patches.items():
        marker = snippet.strip().split("\n")[-1].split("=")[0].strip().split("(")[0]
        marker = marker.replace("export const ", "").replace("export ", "")
        ensure_snippet(data / name, snippet, marker)

    tickets = data / "ticketsData.ts"
    if tickets.exists() and "useTickets" not in tickets.read_text(encoding="utf-8"):
        ensure_snippet(tickets, tickets_stub, "useTickets")

    admin = web_root / "packages" / "shell" / "src" / "lovable" / "components" / "admin" / "AdminPanelView.tsx"
    prod_admin = Path(__file__).resolve().parents[3] / "DoEventsWEB" / "packages" / "shell" / "src" / "lovable" / "components" / "admin" / "AdminPanelView.tsx"
    if prod_admin.exists() and admin.exists():
        prod_text = prod_admin.read_text(encoding="utf-8")
        if "AdminPanelPage" in prod_text and "AdminPanelPage" not in admin.read_text(encoding="utf-8"):
            admin.write_text(prod_text, encoding="utf-8")
            changed.append("AdminPanelView.tsx")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-dir", required=True)
    args = parser.parse_args()
    web = Path(args.web_dir).resolve()
    changed = patch_web(web)
    print(f"patched {len(changed)} files")
    for c in changed:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
