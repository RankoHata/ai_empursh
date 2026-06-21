"""MCP stdio client — manages a single MCP server subprocess.

Communicates via JSON-RPC 2.0 over stdin/stdout.
Each message is a single line of JSON.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from mcp.errors import (
    MCPConnectionError,
    MCPProtocolError,
    MCPServerError,
    MCPTimeoutError,
)
from mcp.protocol import (
    build_initialize_request,
    build_initialized_notification,
    build_tools_call_request,
    build_tools_list_request,
    is_error,
    get_result,
    get_error,
)
from mcp.adapter import mcp_tools_to_openai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 30.0          # seconds
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_BASE_DELAY = 1.0     # seconds
STDIN_CLOSE_TIMEOUT = 2.0      # seconds


# ---------------------------------------------------------------------------
# MCPStdioClient
# ---------------------------------------------------------------------------

class MCPStdioClient:
    """Manages a single MCP server process connected via stdio.

    Usage::

        client = MCPStdioClient(name="filesystem", command="npx",
                                args=["-y", "@anthropic/mcp-server-filesystem", "."])
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "/tmp/foo.txt"})
        await client.disconnect()
    """

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str],
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.cwd = cwd
        self.timeout = timeout

        # Runtime state
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._connected = False
        self._cached_tools: list[dict[str, Any]] = []
        self._reconnect_attempts = 0
        self._shutting_down = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Start the subprocess, handshake, and cache the tool list."""
        async with self._lock:
            await self._connect_locked()

    async def _connect_locked(self) -> None:
        """Internal connect logic — must be called under lock."""

        if self._process is not None:
            await self._cleanup_process()

        logger.info(
            "MCP[%s] Starting: %s %s",
            self.name, self.command, " ".join(self.args),
        )

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
                cwd=self.cwd,
            )
        except Exception as exc:
            logger.error("MCP[%s] Failed to start process: %s", self.name, exc)
            raise MCPConnectionError(f"Failed to start {self.command}: {exc}") from exc

        # Start reading stdout
        self._reader_task = asyncio.create_task(self._read_stdout())

        # Start reading stderr (for logging)
        asyncio.create_task(self._read_stderr())

        try:
            # --- Initialize handshake ---
            self._request_id = 0
            init_result = await self._send_request(
                build_initialize_request(self._next_id()),
                timeout=self.timeout,
            )
            logger.info(
                "MCP[%s] Initialize response: protocol=%s server=%s",
                self.name,
                init_result.get("protocolVersion", "?"),
                init_result.get("serverInfo", {}).get("name", "?"),
            )

            # Send initialized notification
            self._write_line(build_initialized_notification())

            # --- Fetch tool list ---
            tools_result = await self._send_request(
                build_tools_list_request(self._next_id()),
                timeout=self.timeout,
            )
            raw_tools = tools_result.get("tools", [])
            self._cached_tools = raw_tools
            logger.info(
                "MCP[%s] Got %d tools: %s",
                self.name, len(raw_tools),
                [t.get("name", "?") for t in raw_tools],
            )

        except Exception:
            await self._cleanup_process()
            raise

        self._connected = True
        self._reconnect_attempts = 0
        logger.info("MCP[%s] Connected successfully", self.name)

    async def disconnect(self) -> None:
        """Shut down the subprocess and clean up."""
        self._shutting_down = True
        async with self._lock:
            await self._cleanup_process()
            self._connected = False
        self._shutting_down = False

    async def _cleanup_process(self) -> None:
        """Internal: kill the subprocess and cancel reader."""
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None

        # Reject all pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(MCPConnectionError("Connection closed"))
        self._pending.clear()

        if self._process:
            proc = self._process
            self._process = None
            try:
                if proc.returncode is None:
                    # Close stdin first to signal EOF
                    if proc.stdin:
                        try:
                            proc.stdin.close()
                        except Exception:
                            pass
                    # Give it a moment, then kill
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=STDIN_CLOSE_TIMEOUT)
                    except asyncio.TimeoutError:
                        logger.warning("MCP[%s] Process did not exit, killing", self.name)
                        proc.kill()
                        await proc.wait()
            except Exception as exc:
                logger.debug("MCP[%s] Error during cleanup: %s", self.name, exc)

    # ------------------------------------------------------------------
    # Tool access
    # ------------------------------------------------------------------

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return cached tool schemas in OpenAI format."""
        return mcp_tools_to_openai(self.name, self._cached_tools)

    def get_raw_tools(self) -> list[dict[str, Any]]:
        """Return raw MCP tool definitions (from tools/list)."""
        return list(self._cached_tools)

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Invoke a tool on the MCP server and return the result.

        Automatically reconnects once if the connection was lost.
        """
        if self._shutting_down:
            raise MCPConnectionError(f"MCP[{self.name}] is shutting down")

        need_reconnect = not self._connected or self._process is None
        if need_reconnect:
            if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                raise MCPConnectionError(
                    f"MCP[{self.name}] not connected (reconnect attempts exceeded)"
                )
            logger.info("MCP[%s] Reconnecting before call_tool...", self.name)
            await self._reconnect_locked()

        try:
            result = await self._send_request(
                build_tools_call_request(self._next_id(), tool_name, arguments),
                timeout=self.timeout,
            )
            return result
        except MCPConnectionError:
            # Try one more reconnect
            if self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                logger.info("MCP[%s] Connection lost, reconnecting and retrying...", self.name)
                await self._reconnect_locked()
                return await self._send_request(
                    build_tools_call_request(self._next_id(), tool_name, arguments),
                    timeout=self.timeout,
                )
            raise

    async def _reconnect_locked(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        async with self._lock:
            delay = RECONNECT_BASE_DELAY * (2 ** self._reconnect_attempts)
            self._reconnect_attempts += 1
            logger.info(
                "MCP[%s] Reconnect attempt %d/%d (delay=%.1fs)",
                self.name, self._reconnect_attempts, MAX_RECONNECT_ATTEMPTS, delay,
            )
            await asyncio.sleep(delay)
            await self._connect_locked()

    # ------------------------------------------------------------------
    # Internal: send / receive
    # ------------------------------------------------------------------

    async def _send_request(self, payload: bytes, timeout: float) -> dict:
        """Send a request and wait for the matching response."""
        # Extract id from payload for matching
        lines = payload.decode("utf-8").strip().split("\n")
        req_data = json.loads(lines[-1])  # last line (should be the only one)
        req_id = req_data["id"]

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        try:
            self._write_line(payload)
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise MCPTimeoutError(
                f"MCP[{self.name}] Request {req_id} timed out after {timeout}s"
            )
        except Exception:
            self._pending.pop(req_id, None)
            raise

        self._pending.pop(req_id, None)

        # Check if the response is an error
        if is_error(result):
            code, message, data = get_error(result)
            raise MCPServerError(code, message, data)

        return get_result(result)

    def _write_line(self, data: bytes) -> None:
        """Write a line to stdin of the subprocess."""
        if self._process is None or self._process.stdin is None:
            raise MCPConnectionError(f"MCP[{self.name}] stdin is not available")
        try:
            self._process.stdin.write(data)
        except Exception as exc:
            raise MCPConnectionError(f"MCP[{self.name}] write failed: {exc}") from exc

    async def _read_stdout(self) -> None:
        """Continuously read lines from stdout and resolve pending futures."""
        if self._process is None or self._process.stdout is None:
            return

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    # EOF — process exited
                    logger.warning("MCP[%s] stdout EOF (process exited)", self.name)
                    break

                data = line.decode("utf-8").strip()
                if not data:
                    continue

                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("MCP[%s] Non-JSON stdout: %s", self.name, data[:120])
                    continue

                resp_id = msg.get("id")
                if resp_id is not None and resp_id in self._pending:
                    self._pending[resp_id].set_result(msg)
                elif resp_id is not None:
                    logger.debug("MCP[%s] Unexpected response id=%s", self.name, resp_id)
                elif "method" in msg:
                    # Notification from server — log it
                    method = msg.get("method", "?")
                    logger.debug("MCP[%s] Notification: %s", self.name, method)
                else:
                    logger.debug("MCP[%s] Unknown message: %s", self.name, str(msg)[:120])

        except asyncio.CancelledError:
            logger.debug("MCP[%s] Reader cancelled", self.name)
        except Exception as exc:
            logger.error("MCP[%s] Reader error: %s", self.name, exc)

        # If we get here, the process stdout closed unexpectedly
        if not self._shutting_down:
            logger.warning("MCP[%s] Process stdout closed unexpectedly", self.name)
            self._connected = False
            # Reject all pending futures
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(MCPConnectionError("Process stdout closed"))

    async def _read_stderr(self) -> None:
        """Continuously read stderr and log it."""
        if self._process is None or self._process.stderr is None:
            return

        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.debug("MCP[%s] stderr: %s", self.name, text)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("MCP[%s] Stderr reader error: %s", self.name, exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _build_env(self) -> Optional[dict[str, str]]:
        """Build the environment dict for the subprocess.

        Merges the parent process environment with any user-specified overrides.
        Respects NO_PROXY for API access.
        """
        env = dict(os.environ)
        if self.env:
            env.update(self.env)
        return env

    @property
    def connected(self) -> bool:
        return self._connected
