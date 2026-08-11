"""挂给对话模型的写记忆工具。

读是白给的（档案在提示词里已经拼好了），写必须由模型主动决定：哪句闲聊值得
记一辈子、哪条旧记录已经不成立，只有看得懂上下文的模型分得清。

模型只能写本轮上下文里出现过的人：user_id 是它从聊天记录里抄来的，
抄错一位就把张三的事记到李四头上，所以这里挡一道。
"""

from nonebot import logger
from pydantic_ai import Agent, ModelRetry

from src.providers.user_memory import append_memory, replace_memory


def _choices(participants: dict[str, str]) -> str:
    return "、".join(f"{name}(id:{uid})" for uid, name in participants.items())


def register(agent: Agent, participants: dict[str, str]) -> None:
    """把写记忆的工具挂到 agent 上。

    participants 为本轮上下文里出现过的 ``用户 id -> 展示名``。
    """

    def check(user_id: str) -> str:
        name = participants.get(user_id)
        if name is None:
            raise ModelRetry(
                f"user_id {user_id!r} 不在当前对话里。"
                f"只能记录这几位：{_choices(participants)}"
            )
        return name

    @agent.tool_plain
    async def remember(user_id: str, note: str) -> str:
        """记下关于某位群友的一条长期信息，之后聊天时我会一直记得。

        只记以后还用得上的稳定信息：身份、职业、所在地、口味偏好与忌口、
        长期在做的事、希望被怎么称呼。不要记一次性的闲聊、当下的情绪、
        或者你自己的推测。档案里已经有的事不用重复记。

        Args:
            user_id: 群友的 id，从聊天记录里 `名字(id:xxx)` 的括号中抄。
            note: 一句话陈述句，例如「广州人，在天河上班」「不吃香菜」。
        """
        name = check(user_id)
        try:
            content = await append_memory(user_id, note)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        logger.info(f"记住了 {name}({user_id}) 的一条记忆：{note}")
        return f"已记住关于 {name} 的这条。当前档案：\n{content}"

    @agent.tool_plain
    async def update_memory(user_id: str, old: str, new: str) -> str:
        """改掉或删掉某位群友档案里已有的一条记忆。

        发现旧记录不成立了（搬家了、换工作了、口味变了）就用它更新；
        对方明确要求忘掉某件事时，把 new 传空字符串即可删除。

        Args:
            user_id: 群友的 id，从聊天记录里 `名字(id:xxx)` 的括号中抄。
            old: 档案里要被替换掉的原文，照抄那一条。
            new: 换成的新内容；传空字符串表示删除这一条。
        """
        name = check(user_id)
        try:
            content = await replace_memory(user_id, old, new)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        if content is None:
            raise ModelRetry(
                f"{name} 的档案里没找到 {old!r}，请照抄档案里已有的原文，"
                "或者改用 remember 记一条新的"
            )
        action = "删除" if not new.strip() else "更新"
        logger.info(f"{action}了 {name}({user_id}) 的一条记忆：{old!r} -> {new!r}")
        return f"已{action}。{name} 的当前档案：\n{content or '（已清空）'}"
