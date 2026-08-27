from contextlib import asynccontextmanager

import pytest

from open_webui.models.video_generation import VideoGenerationJob
from open_webui.utils import video_generation


def _job(job_id: str, *, status: str, next_poll_at: int, lease_until: int | None):
    return VideoGenerationJob(
        id=job_id,
        user_id='video-user',
        chat_id=None,
        message_id=None,
        provider='minimax',
        model='MiniMax-H3',
        prompt='A quiet lake',
        input_mode='text',
        request_payload={'options': {'duration': 5}},
        status=status,
        next_poll_at=next_poll_at,
        lease_until=lease_until,
        created_at=1,
        updated_at=1,
    )


@pytest.mark.asyncio
async def test_claim_due_video_jobs_reclaims_expired_leases_after_restart(db_session, monkeypatch):
    due = _job('due-job', status='running', next_poll_at=90, lease_until=50)
    queued = _job('queued-job', status='queued', next_poll_at=95, lease_until=None)
    leased = _job('leased-job', status='running', next_poll_at=80, lease_until=200)
    terminal = _job('terminal-job', status='failed', next_poll_at=80, lease_until=None)
    db_session.add_all([due, queued, leased, terminal])
    await db_session.commit()

    @asynccontextmanager
    async def reuse_session(_db=None):
        yield db_session

    monkeypatch.setattr(video_generation, 'get_async_db_context', reuse_session)

    first_claim = await video_generation._claim_due_video_jobs(now=100, limit=2)
    assert first_claim == ['due-job', 'queued-job']
    assert due.lease_until == 190
    assert queued.lease_until == 190

    second_claim = await video_generation._claim_due_video_jobs(now=200, limit=2)
    assert second_claim == ['due-job', 'queued-job']
    assert due.lease_until == 290
    assert queued.lease_until == 290
