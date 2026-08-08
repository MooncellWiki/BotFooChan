import asyncio
from collections import deque
from datetime import datetime

from nonebot.log import logger
from nonebot_plugin_alconna.uniseg import CustomNode, Reference, Target, UniMessage

from .plugin_config import plugin_config

QUEUE: deque[tuple[Target, UniMessage, int]] = deque()

MESSGE_SEND_INTERVAL = 1.5

_MESSAGE_DISPATCH_TASKS: set[asyncio.Task] = set()


def _fill_forward_sender(msg: UniMessage, self_id: str) -> None:
    """给合并转发的节点补上发送者 id

    组装消息时还不知道会用哪个 bot 发，所以 ``_to_forward`` 先留空，发送前再填。
    """
    for seg in msg:
        if isinstance(seg, Reference):
            for node in seg.children:
                if isinstance(node, CustomNode) and not node.uid:
                    node.uid = self_id


async def _do_send(send_target: Target, msg: UniMessage):
    bot = await send_target.select()
    _fill_forward_sender(msg, bot.self_id)
    await msg.send(target=send_target, bot=bot)


async def do_send_msgs():
    while QUEUE:
        # why read from queue then pop item from queue?
        # if there is only 1 item in queue, pop it and await send
        # the length of queue will be 0.
        # At that time, adding items to queue will trigger a new execution of this func,
        # which is not expected.
        # So, read from queue first then pop from it
        send_target, msg, retry_time = QUEUE[0]
        try:
            await _do_send(send_target, msg)
        except Exception as e:
            await asyncio.sleep(MESSGE_SEND_INTERVAL)
            QUEUE.popleft()
            if retry_time > 0:
                QUEUE.appendleft((send_target, msg, retry_time - 1))
            else:
                msg_str = str(msg)
                if len(msg_str) > 50:
                    msg_str = msg_str[:50] + "..."
                logger.warning(f"send msg err {e} {msg_str}")
        else:
            # sleeping after popping may also cause re-execution error
            # like above mentioned
            await asyncio.sleep(MESSGE_SEND_INTERVAL)
            QUEUE.popleft()


async def _send_msgs_dispatch(send_target: Target, msg: UniMessage):
    if plugin_config.bison_use_queue:
        QUEUE.append((send_target, msg, plugin_config.bison_resend_times))
        # len(QUEUE) before append was 0
        if len(QUEUE) == 1:
            task = asyncio.create_task(do_send_msgs())
            _MESSAGE_DISPATCH_TASKS.add(task)
            task.add_done_callback(_MESSAGE_DISPATCH_TASKS.discard)
    else:
        await _do_send(send_target, msg)


def _to_forward(msgs: list[UniMessage]) -> UniMessage:
    """把多条消息包成合并转发

    uniseg 的 Reference 要求每个节点带上发送者，uid 留空、发送时由
    ``_fill_forward_sender`` 填成实际的 bot id。
    """
    now = datetime.now().astimezone()
    return UniMessage(
        Reference(
            nodes=[
                CustomNode(uid="", name="bison", content=msg, time=now) for msg in msgs
            ]
        )
    )


async def send_msgs(send_target: Target, msgs: list[UniMessage]):
    if not plugin_config.bison_use_pic_merge:
        for msg in msgs:
            await _send_msgs_dispatch(send_target, msg)
        return
    msgs = msgs.copy()
    if plugin_config.bison_use_pic_merge == 1:
        await _send_msgs_dispatch(send_target, msgs.pop(0))
    if msgs:
        if len(msgs) == 1:  # 只有一条消息序列就不合并转发
            await _send_msgs_dispatch(send_target, msgs.pop(0))
        else:
            await _send_msgs_dispatch(send_target, _to_forward(msgs))
