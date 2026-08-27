import asyncio

import open_webui.tasks as task_registry
import pytest


@pytest.mark.asyncio
async def test_failed_remote_registration_cancels_local_task_before_dispatch(monkeypatch):
    dispatch_gate = asyncio.Event()
    provider_calls = []

    async def provider_task():
        await dispatch_gate.wait()
        provider_calls.append('dispatched')

    async def fail_registration(*_args, **_kwargs):
        raise RuntimeError('injected task registration failure')

    monkeypatch.setattr(task_registry, 'redis_save_task', fail_registration)

    with pytest.raises(RuntimeError, match='injected task registration failure'):
        await task_registry.create_task(
            object(),
            provider_task(),
            id='chat-1',
            task_id='task-1',
        )

    dispatch_gate.set()
    await asyncio.sleep(0)

    assert provider_calls == []
    assert 'task-1' not in task_registry.tasks
    assert 'chat-1' not in task_registry.item_tasks


@pytest.mark.asyncio
async def test_stop_item_tasks_cancels_every_local_task_when_registry_mutates():
    item_id = 'chat-with-four-tasks'
    task_ids = [f'local-task-{index}' for index in range(4)]
    cancelled = []
    created_tasks = []

    async def wait_until_cancelled(index):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.append(index)
            raise

    try:
        for index, task_id in enumerate(task_ids):
            _, task = await task_registry.create_task(
                None,
                wait_until_cancelled(index),
                id=item_id,
                task_id=task_id,
            )
            created_tasks.append(task)

        await asyncio.sleep(0)

        result = await task_registry.stop_item_tasks(None, item_id)

        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert result['status'] is True
        assert sorted(cancelled) == list(range(4))
        assert all(task.cancelled() for task in created_tasks)
        assert all(task_id not in task_registry.tasks for task_id in task_ids)
        assert item_id not in task_registry.item_tasks
    finally:
        for task in created_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*created_tasks, return_exceptions=True)
        for task_id in task_ids:
            await task_registry.cleanup_task(None, task_id, item_id)


@pytest.mark.asyncio
async def test_unscoped_tasks_do_not_leak_into_item_index():
    async def complete_immediately():
        return None

    task_id, task = await task_registry.create_task(None, complete_immediately(), task_id='unscoped-task')
    await task
    await asyncio.sleep(0)

    assert task_id not in task_registry.tasks
    assert None not in task_registry.item_tasks
