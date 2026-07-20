"""Integration test placeholder for LangGraph checkpoint persistence.

LangGraph has not yet been integrated into the agent pipeline. These tests
serve as a specification for the checkpoint behaviour that will be validated
once the LangGraph integration lands.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="LangGraph not yet integrated")
class TestCheckpointPersistence:
    """Verify that conversation state is checkpointed across turns.

    Once LangGraph is wired in, these tests should:
    - Confirm a checkpoint is created after the first /ask call
    - Confirm a subsequent /ask with the same conversation_id resumes state
    - Confirm checkpoint survives a process restart (using SQLite or Postgres)
    """

    async def test_checkpoint_created_after_first_turn(self, api_client):
        """After the first message in a conversation, a checkpoint row should exist."""
        raise NotImplementedError

    async def test_checkpoint_restored_on_followup(self, api_client):
        """A follow-up message in the same conversation should load prior state."""
        raise NotImplementedError

    async def test_checkpoint_survives_restart(self, api_client):
        """Checkpoint data should persist when the application restarts."""
        raise NotImplementedError

    async def test_checkpoint_isolates_conversations(self, api_client):
        """Different conversation_ids should have independent checkpoints."""
        raise NotImplementedError
