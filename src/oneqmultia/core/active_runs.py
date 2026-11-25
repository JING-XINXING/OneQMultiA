"""进行中的问答轮次登记，供 WebSocket 断线后按 qa_pair_id 幂等续订。

事件先写入内存缓冲，再分发给当前订阅队列。新订阅者先拿到历史事件，
再接收后续 platform_done / complete，避免重连后重新创建提问。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActiveRun:
    """一轮仍在执行或刚结束、可供续订的问答。"""

    qa_pair_id: str
    session_id: str
    question: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    queues: List[asyncio.Queue] = field(default_factory=list)
    done: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def publish(self, event: Dict[str, Any]) -> None:
        """记录并广播一条可 JSON 序列化的事件。"""
        async with self.lock:
            self.events.append(event)
            queues = list(self.queues)
        for queue in queues:
            queue.put_nowait(event)

    async def finish(self) -> None:
        """标记结束，并让每个订阅队列收到 None 作为哨兵。"""
        async with self.lock:
            self.done = True
            queues = list(self.queues)
            self.queues.clear()
        for queue in queues:
            queue.put_nowait(None)

    async def subscribe(self) -> asyncio.Queue:
        """订阅：先回放已有事件；若已结束则立刻送出结束哨兵。"""
        queue: asyncio.Queue = asyncio.Queue()
        async with self.lock:
            for event in self.events:
                queue.put_nowait(event)
            if self.done:
                queue.put_nowait(None)
            else:
                self.queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """连接断开时摘掉队列，不中断后台问答任务。"""
        try:
            self.queues.remove(queue)
        except ValueError:
            return


class ActiveRunRegistry:
    """进程内登记表。按 qa_pair_id 查找，并避免同一会话同一问题重复开跑。"""

    def __init__(self) -> None:
        self._runs: Dict[str, ActiveRun] = {}

    def put(self, run: ActiveRun) -> None:
        self._runs[run.qa_pair_id] = run
        # 只留最近 50 轮，避免长时间运行把缓冲撑大
        if len(self._runs) > 50:
            oldest = next(iter(self._runs))
            self._runs.pop(oldest, None)

    def get(self, qa_pair_id: str) -> Optional[ActiveRun]:
        return self._runs.get(qa_pair_id)

    def find_open(self, session_id: str, question: str) -> Optional[ActiveRun]:
        """同一会话、同一问题仍在跑时复用，避免断线重连再插一条 QAPair。"""
        for run in self._runs.values():
            if run.session_id == session_id and run.question == question and not run.done:
                return run
        return None


# 应用级单例：WebSocket 入口与测试共用
registry = ActiveRunRegistry()
