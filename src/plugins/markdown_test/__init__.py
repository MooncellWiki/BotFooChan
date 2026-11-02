"""/mdtest：让 QQ 官方机器人发一条原生 markdown，看看本群、本机器人能不能发（仅超管）。

原生 markdown（``markdown.content``）要开通权限，各种语法支持到什么程度也只能实测。
不带内容时发一段覆盖常用语法的示例；带内容就原样当 markdown 发（换行保留）。

- 默认是被动回复（带触发消息的 msg_id）
- ``-p`` 改发主动消息，和通用对话长回答、OneBot 推送走的是同一种，受主动消息额度限制

发不出去时把接口的错误码、错误信息、trace id 回给超管。只在官方机器人上响应，
``/官q 关`` 停用的群里也照样能用（见 :mod:`src.plugins.qq_official`）。
"""

from nonebot import logger, on_command
from nonebot.adapters import Bot, Event, Message
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq import (
    C2CMessageCreateEvent,
    GroupMessageCreateEvent,
    MessageEvent,
)
from nonebot.adapters.qq import MessageSegment as QQMS
from nonebot.adapters.qq.exception import ActionFailed, AuditException
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    "markdown 测试",
    "让 QQ 官方机器人发一条原生 markdown，测试发送权限和语法支持（仅超管）",
    "/mdtest：发一段示例\n"
    "/mdtest <内容>：把内容当 markdown 发\n"
    "/mdtest -p [内容]：改发主动消息",
    supported_adapters={"~qq"},
)

PROACTIVE_FLAGS = ("-p", "--proactive")


def sample(bot: QQBot) -> str:
    lines = [
        "# 一级标题",
        "## 二级标题",
        "**加粗** *斜体* ~~删除线~~ `行内代码`",
        "",
        "- 无序列表一",
        "- 无序列表二",
        "",
        "1. 有序列表一",
        "2. 有序列表二",
        "",
        "> 引用",
        "",
        "***",
        "",
        "```python",
        'print("代码块")',
        "```",
        "",
        "| 表头 | 表头 |",
        "| --- | --- |",
        "| 单元格 | 单元格 |",
        "",
        "[链接：QQ 机器人文档](https://bot.q.qq.com/wiki/)",
    ]
    # 图片用机器人自己的头像，不依赖外部地址；``#宽px #高px`` 是 QQ 要求的尺寸写法
    if avatar := bot.self_info.avatar:
        lines += ["", f"![头像 #100px #100px]({avatar})"]
    return "\n".join(lines)


async def _is_official(bot: Bot, event: Event) -> bool:
    return isinstance(bot, QQBot) and isinstance(event, MessageEvent)


mdtest = on_command(
    "mdtest",
    rule=_is_official,
    aliases={"markdown测试"},
    permission=SUPERUSER,
    block=True,
)


@mdtest.handle()
async def _(bot: QQBot, event: MessageEvent, arg: Message = CommandArg()) -> None:
    content = arg.extract_plain_text().strip()
    head, *rest = content.split(maxsplit=1) or [""]
    if proactive := head in PROACTIVE_FLAGS:
        content = rest[0] if rest else ""
    message = QQMS.markdown(content or sample(bot))

    try:
        if not proactive:
            await bot.send(event, message)
        elif isinstance(event, GroupMessageCreateEvent):
            await bot.send_to_group(event.group_openid, message)
        elif isinstance(event, C2CMessageCreateEvent):
            await bot.send_to_c2c(event.author.id, message)
        else:
            await mdtest.finish("主动消息只测群聊和单聊")
    except AuditException as e:
        await mdtest.finish(f"markdown 进了审核，audit_id={e.audit_id}")
    except ActionFailed as e:
        logger.opt(exception=e).warning("markdown 测试发送失败")
        await mdtest.finish(
            "markdown 发送失败"
            f"（{'主动' if proactive else '被动'}消息）\n"
            f"HTTP {e.status_code}，code={e.code}\n"
            f"message={e.message}\n"
            f"trace_id={e.trace_id}"
        )
