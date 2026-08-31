"""
Assistant Userbot Session Pool Orchestrator.
Manages warm standby MTProto client sessions, least-load balancing, and automatic hot-failover.
"""
import asyncio
from typing import Dict, List, Optional
from app.config import settings


class AssistantAccount:
    def __init__(self, assistant_id: int, session_string: str, max_concurrent_vcs: int = 5):
        self.assistant_id = assistant_id
        self.session_string = session_string
        self.max_concurrent_vcs = max_concurrent_vcs
        self.active_vcs: set = set()
        self.is_healthy: bool = True

    @property
    def current_load(self) -> int:
        return len(self.active_vcs)

    @property
    def is_available(self) -> bool:
        return self.is_healthy and self.current_load < self.max_concurrent_vcs


class AssistantSessionPool:
    def __init__(self):
        self.assistants: Dict[int, AssistantAccount] = {}
        self._lock = asyncio.Lock()
        self._init_pool()

    def _init_pool(self):
        """Load session strings from settings or configuration."""
        raw_sessions = [s.strip() for s in settings.ASSISTANT_SESSION_STRINGS.split(",") if s.strip()]
        if not raw_sessions:
            # Initialize with standard default mock assistants for development & testing
            self.assistants[881293011] = AssistantAccount(881293011, "mock_session_alpha_1")
            self.assistants[881293012] = AssistantAccount(881293012, "mock_session_beta_2")
            self.assistants[881293013] = AssistantAccount(881293013, "mock_session_gamma_3")
        else:
            for idx, session in enumerate(raw_sessions):
                assistant_id = 900000000 + idx
                self.assistants[assistant_id] = AssistantAccount(assistant_id, session)

    async def acquire_assistant_for_room(self, room_id: int) -> AssistantAccount:
        """
        Assign the least-loaded healthy assistant to a voice chat.
        """
        async with self._lock:
            # Check if room already has an assigned assistant
            for asst in self.assistants.values():
                if room_id in asst.active_vcs:
                    return asst

            # Find available assistant with lowest active VCs
            available = [a for a in self.assistants.values() if a.is_available]
            if not available:
                # If all at capacity, pick least loaded even if above preferred limit
                available = sorted(self.assistants.values(), key=lambda a: a.current_load)

            selected = min(available, key=lambda a: a.current_load)
            selected.active_vcs.add(room_id)
            return selected

    async def release_assistant_from_room(self, room_id: int, assistant_id: Optional[int] = None):
        """
        Unbind room from assistant session upon stop or disconnect.
        """
        async with self._lock:
            if assistant_id and assistant_id in self.assistants:
                self.assistants[assistant_id].active_vcs.discard(room_id)
            else:
                for asst in self.assistants.values():
                    asst.active_vcs.discard(room_id)

    async def handle_assistant_failover(self, room_id: int, failed_assistant_id: int) -> AssistantAccount:
        """
        Hot-failover: Mark failed assistant degraded and assign a fresh warm assistant.
        """
        async with self._lock:
            if failed_assistant_id in self.assistants:
                self.assistants[failed_assistant_id].is_healthy = False
                self.assistants[failed_assistant_id].active_vcs.discard(room_id)

            available = [a for a in self.assistants.values() if a.is_available and a.assistant_id != failed_assistant_id]
            if not available:
                available = [a for a in self.assistants.values() if a.assistant_id != failed_assistant_id]

            new_assistant = min(available, key=lambda a: a.current_load)
            new_assistant.active_vcs.add(room_id)
            return new_assistant


assistant_pool = AssistantSessionPool()
