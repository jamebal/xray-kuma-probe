import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.utils.redact import redact

logger = logging.getLogger(__name__)


class XrayManager:
    def __init__(self, binary: Path, config_path: Path, max_backoff: float = 60) -> None:
        self.binary = binary
        self.config_path = config_path
        self.max_backoff = max_backoff
        self.process: asyncio.subprocess.Process | None = None
        self._supervisor: asyncio.Task[None] | None = None
        self._stopping = False

    async def install_config(self, config: dict[str, Any]) -> bool:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="xray-", suffix=".json", dir=self.config_path.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(config, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            check = await asyncio.create_subprocess_exec(
                str(self.binary),
                "run",
                "-test",
                "-config",
                str(temp),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await check.communicate()
            if check.returncode != 0:
                logger.error(
                    "xray_config_invalid error=%s", redact(stderr.decode(errors="replace"))
                )
                return False
            os.replace(temp, self.config_path)
            return True
        finally:
            temp.unlink(missing_ok=True)

    async def start(self) -> None:
        self._stopping = False
        if self._supervisor is None or self._supervisor.done():
            self._supervisor = asyncio.create_task(self._supervise(), name="xray-supervisor")

    async def _supervise(self) -> None:
        backoff = 1.0
        while not self._stopping:
            self.process = await asyncio.create_subprocess_exec(
                str(self.binary),
                "run",
                "-config",
                str(self.config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            readers = [
                asyncio.create_task(self._read_stream(self.process.stdout)),
                asyncio.create_task(self._read_stream(self.process.stderr)),
            ]
            code = await self.process.wait()
            await asyncio.gather(*readers)
            self.process = None
            if self._stopping:
                return
            logger.error("xray_exited code=%d retry_seconds=%.1f", code, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.max_backoff)

    async def _read_stream(self, stream: asyncio.StreamReader | None) -> None:
        if stream is None:
            return
        async for line in stream:
            logger.warning("xray_output message=%s", redact(line.decode(errors="replace").strip()))

    async def restart(self) -> None:
        await self._stop_process()

    async def _stop_process(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 10)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()

    async def stop(self) -> None:
        self._stopping = True
        await self._stop_process()
        if self._supervisor:
            await self._supervisor
