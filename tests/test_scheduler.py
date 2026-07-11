import asyncio

import pytest

from app.main import run_fixed_interval


@pytest.mark.asyncio
async def test_fixed_interval_does_not_add_action_duration() -> None:
    starts: list[float] = []
    stop = asyncio.Event()

    async def action() -> None:
        starts.append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.02)
        if len(starts) == 3:
            stop.set()

    await run_fixed_interval(action, 0.05, stop)

    assert starts[1] - starts[0] == pytest.approx(0.05, abs=0.015)
    assert starts[2] - starts[1] == pytest.approx(0.05, abs=0.015)
