"""In-process live-event hub: the bridge between the event workers and any
connected browser (Hub, Companion). Workers and the FastAPI app share one
process and one asyncio loop (evoke_workers_loop is a startup task in
main.py), so no extra broker is needed — the worker calls broadcast() as
it processes each stream event, and every open /ws socket gets a push.

Deliberately fire-and-forget: a dead/slow browser socket must never block
or crash event processing, so sends are scheduled as independent tasks and
any send failure just drops that socket from the set. This is a UI
freshness channel, not a delivery guarantee — the source of truth stays
the projections/APIs the screens already load on render; the live push
only tells them "something changed, here's what" so they can update
without polling.
"""

import asyncio
import json


class LiveHub:
    def __init__(self):
        self.connections = set()

    def register(self, ws):
        self.connections.add(ws)

    def unregister(self, ws):
        self.connections.discard(ws)

    def broadcast(self, message: dict):
        """Safe to call from sync code running inside the event loop (the
        worker's _process_event). Outside a running loop, silently no-ops —
        e.g. unit tests importing workers.py directly."""
        if not self.connections:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        data = json.dumps(message, default=str)
        for ws in list(self.connections):
            loop.create_task(self._send(ws, data))

    async def _send(self, ws, data: str):
        try:
            await ws.send_text(data)
        except Exception:
            self.unregister(ws)


live_hub = LiveHub()
