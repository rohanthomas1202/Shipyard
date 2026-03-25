"""Tests for TokenBatcher — buffers events and flushes on interval."""
import asyncio
import logging
import pytest
from agent.events import TokenBatcher


@pytest.mark.asyncio
async def test_batcher_flushes_after_interval():
    flushed = []
    async def on_flush(items):
        flushed.extend(items)
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)
    batcher.add("token1")
    batcher.add("token2")
    assert len(flushed) == 0
    await asyncio.sleep(0.1)
    assert flushed == ["token1", "token2"]
    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_empty_buffer_no_flush():
    flush_count = 0
    async def on_flush(items):
        nonlocal flush_count
        flush_count += 1
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)
    await asyncio.sleep(0.15)
    assert flush_count == 0
    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_multiple_flushes():
    batches = []
    async def on_flush(items):
        batches.append(list(items))
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)
    batcher.add("a")
    await asyncio.sleep(0.08)
    batcher.add("b")
    await asyncio.sleep(0.08)
    assert len(batches) >= 2
    assert batches[0] == ["a"]
    assert batches[1] == ["b"]
    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_stop_flushes_remaining():
    flushed = []
    async def on_flush(items):
        flushed.extend(items)
    batcher = TokenBatcher(flush_interval=1.0)
    batcher.start(on_flush)
    batcher.add("final_item")
    await batcher.stop()
    assert "final_item" in flushed


@pytest.mark.asyncio
async def test_batcher_stop_idempotent():
    batcher = TokenBatcher(flush_interval=0.05)
    async def on_flush(items): pass
    batcher.start(on_flush)
    await batcher.stop()
    await batcher.stop()  # no error


@pytest.mark.asyncio
async def test_batcher_start_idempotent():
    call_count = 0
    async def on_flush(items):
        nonlocal call_count
        call_count += 1
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)
    batcher.start(on_flush)  # second call should be no-op
    batcher.add("x")
    await asyncio.sleep(0.1)
    assert call_count == 1  # only one flush loop running
    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_catches_flush_errors():
    async def bad_flush(items):
        raise RuntimeError("flush failed")
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(bad_flush)
    batcher.add("item")
    await asyncio.sleep(0.1)  # should not crash
    batcher.add("item2")
    await asyncio.sleep(0.1)  # still running
    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_not_started():
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.add("item")
    assert len(batcher._buffer) == 1
