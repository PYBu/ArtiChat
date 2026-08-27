from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace


MAIN_PATH = Path(__file__).resolve().parents[1] / 'open_webui' / 'main.py'


def _load_task_helpers():
    tree = ast.parse(MAIN_PATH.read_text(encoding='utf-8'))
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.name in {'_create_background_task', '_cancel_background_task'}
    ]
    module = ast.Module(body=functions, type_ignores=[])
    namespace = {
        'FastAPI': object,
        'asyncio': asyncio,
        'log': logging.getLogger('test.background-task-lifecycle'),
    }
    exec(compile(ast.fix_missing_locations(module), str(MAIN_PATH), 'exec'), namespace)
    return namespace['_create_background_task'], namespace['_cancel_background_task']


def test_lifespan_registers_every_long_lived_task():
    source = MAIN_PATH.read_text(encoding='utf-8')
    for name in (
        'license_data',
        'redis_task_command_listener',
        'usage_pool_cleanup',
        'session_pool_cleanup',
        'reservation_cleanup',
        'scheduler_worker',
    ):
        assert f"_create_background_task(app, '{name}'" in source or f"'{name}'," in source

    assert 'for name, task in tuple(app.state.background_tasks.items())' in source
    assert 'app.state.background_tasks.clear()' in source


def test_registered_background_task_is_cancelled_and_awaited():
    async def exercise():
        create_background_task, cancel_background_task = _load_task_helpers()
        app = SimpleNamespace(state=SimpleNamespace(background_tasks={}))
        stopped = asyncio.Event()

        async def worker():
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        task = create_background_task(app, 'worker', worker())
        await asyncio.sleep(0)

        assert app.state.background_tasks['worker'] is task
        await cancel_background_task(task, 'worker', timeout=0.2)

        assert task.cancelled()
        assert stopped.is_set()

    asyncio.run(exercise())
