from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from arclet.alconna import AllParam
import httpx
from nonebot import get_plugin_config, logger
from nonebot.internal.adapter import Bot, Event
from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna
from nonebot_plugin_alconna.builtins.extensions.reply import ReplyRecordExtension
from nonebot_plugin_alconna.builtins.uniseg.market_face import MarketFace
from nonebot_plugin_alconna.uniseg import (
    Image,
    MsgId,
    Reference,
    Reply,
    Text,
    UniMessage,
    message_reaction,
)

from src.providers.chat_history import HistoryWindow, format_records, scope_id
from src.providers.llm import UsageTracker, resolve_endpoint
from src.providers.llm.media import as_model_inputs

from .config import Config
from .processors.ai import generate_ai_response
from .processors.pdf import process_pdf
from .processors.web import process_web_page
from .reply import send_answer

# 从文件加载系统提示词
SYSTEM_PROMPT_RAW = (
    Path(__file__).parent.joinpath("prompt.txt").read_text(encoding="utf-8")
)
SEARCH_PROMPT = """
## 联网搜索
- 你可以联网搜索
- 遇到不认识的新词、网络梗、近期事件或拿不准的事实，先搜索再解释，不要凭印象编造
- 搜索只是帮你弄懂内容，最终仍然只按约定输出一个 json 对象
- 今天是 {today:%Y-%m-%d}"""
"""开启联网搜索时追加在系统提示词之后；不给日期的话模型连「近期」指什么都不知道"""
TZ = ZoneInfo("Asia/Shanghai")
config = get_plugin_config(Config)

zssm = on_alconna(
    Alconna("zssm", Args["content?", AllParam]), extensions=[ReplyRecordExtension()]
)


@zssm.handle()
async def handle(
    msg_id: MsgId,
    ext: ReplyRecordExtension,
    event: Event,
    bot: Bot,
    content: Match[UniMessage],
):
    """处理zssm命令

    Args:
        msg_id: 消息ID
        ext: 回复记录扩展
        event: 事件对象
        bot: 机器人对象
        content: 消息内容
    """
    msg = event.get_message()
    tracker = UsageTracker()
    system_prompt = SYSTEM_PROMPT_RAW
    if config.zssm_ai_web_search:
        system_prompt += SEARCH_PROMPT.format(today=datetime.now(TZ))
    user_prompt = ""
    image_list: list[Image] = []
    url_pattern = r"\b(?:https?):\/\/[^\s\/?#]+[^\s]*\b"
    pdf_pattern = r"\b(?:https?):\/\/[^\s\/?#]+[^\s]*\.pdf\b"
    raw_user_input = ""

    # 处理回复消息
    reply = ext.get_reply(msg_id)
    if reply:
        reply_msg_raw = reply.msg

        if not reply_msg_raw:
            return await UniMessage(Text("上一条消息内容为空")).send(
                reply_to=Reply(msg_id)
            )

        if isinstance(reply_msg_raw, str):
            reply_msg_raw = msg.__class__(reply_msg_raw)

        reply_msg = UniMessage.generate_sync(message=reply_msg_raw)  # pyright: ignore[reportAttributeAccessIssue]

        reply_msg_display = ""
        for item in reply_msg:
            if isinstance(item, Image):
                # 图片按出现顺序编号，与随消息附上的图片一一对应
                image_list.append(item)
                reply_msg_display += f"[图片 {len(image_list)}]"
            elif isinstance(item, Reference):
                return await UniMessage(Text("不支持引用消息")).send(
                    reply_to=Reply(msg_id)
                )
            elif isinstance(item, MarketFace):
                return await UniMessage(Text("不支持商城表情")).send(
                    reply_to=Reply(msg_id)
                )
            else:
                reply_msg_display += str(item)

        user_prompt += f"<type: text>\n{reply_msg_display}\n</type: text>"
        raw_user_input += reply_msg_display

    # 处理输入内容
    if content.available:
        any_content = content.result

        any_content_display = ""
        for item in any_content:
            if isinstance(item, Image):
                image_list.append(item)
                any_content_display += f"[图片 {len(image_list)}]"
            else:
                any_content_display += str(item)

        if reply:
            user_prompt += f"<type: interest>\n{any_content_display}\n</type: interest>"
        else:
            user_prompt += f"<type: text>\n{any_content_display}\n</type: text>"
        raw_user_input += any_content_display

    if not user_prompt and not image_list:
        return await UniMessage(Text("请回复或输入内容")).send(reply_to=Reply(msg_id))

    # 验证API配置
    endpoint = resolve_endpoint(config.zssm_ai_model) if config.zssm_ai_model else None
    if endpoint is None:
        return await UniMessage(Text("未配置 AI 模型, 暂时无法使用")).send(
            reply_to=Reply(msg_id)
        )

    await message_reaction("424", msg_id, event, bot)

    # 处理图片, 最多2张
    if len(image_list) > 2:
        return await UniMessage(Text("图片数量超过限制, 最多 2 张")).send(
            reply_to=Reply(msg_id)
        )

    # 图片直接交给模型看，不再先让另一个模型转述成文字
    image_inputs = []
    if image_list:
        if not endpoint.supports_vision:
            return await UniMessage(
                Text(f"当前模型 {config.zssm_ai_model} 看不了图片")
            ).send(reply_to=Reply(msg_id))
        with tracker.stage("读取图片"):
            image_inputs = await as_model_inputs(image_list)
        # 少一张 [图片 N] 就对不上号了，干脆整体报错
        if len(image_inputs) < len(image_list):
            return await UniMessage(Text("图片获取失败")).send(reply_to=Reply(msg_id))

    # 处理URL和PDF - 只从原始用户输入中提取URL，而不是从完整的user_prompt中提取
    msg_urls = re.findall(url_pattern, raw_user_input)

    if msg_urls:
        # 尝试处理第一个链接
        url = msg_urls[0]
        logger.info(f"处理URL: {url}")

        # 尝试检测链接内容类型
        try:
            async with httpx.AsyncClient() as client:
                head_response = await client.head(url, follow_redirects=True)
                content_type = head_response.headers.get("Content-Type", "").lower()
                is_pdf = re.match(pdf_pattern, url) or "application/pdf" in content_type
                logger.info(f"链接内容类型: {content_type} - {head_response.url}")
        except Exception:
            # 如果HEAD请求失败，使用URL后缀判断
            is_pdf = re.match(pdf_pattern, url)

        if is_pdf:
            # 处理PDF链接
            await UniMessage(Text("正在尝试处理PDF文件")).send(reply_to=Reply(msg_id))

            with tracker.stage("读取链接"):
                pdf_content = await process_pdf(url)
            if pdf_content:
                user_prompt += f"\n<type: pdf, url: {url}>\n{pdf_content}\n</type: pdf>"
            else:
                return await UniMessage(
                    Text("无法处理PDF文件，请检查文件是否有效且大小合适")
                ).send(reply_to=Reply(msg_id))
        else:
            # 处理普通网页链接
            await UniMessage(Text("正在尝试打开链接")).send(reply_to=Reply(msg_id))

            with tracker.stage("读取链接"):
                page_content = await process_web_page(url)
            if page_content:
                user_prompt += (
                    f"\n<type: web_page, url: {url}>\n{page_content}\n</type: web_page>"
                )
            else:
                # 最后尝试作为PDF处理
                with tracker.stage("读取链接"):
                    pdf_content = await process_pdf(url)
                if pdf_content:
                    user_prompt += (
                        f"\n<type: pdf, url: {url}>\n{pdf_content}\n</type: pdf>"
                    )
                else:
                    return await UniMessage(Text("无法获取页面内容")).send(
                        reply_to=Reply(msg_id)
                    )

    # 如果处理了URL/PDF或图片, 更新反应
    if msg_urls or image_list:
        await message_reaction("314", msg_id, event, bot)

    # 附带被解释内容之前的几条聊天，更早的交给模型用工具自己翻。
    # 回复了某条就锚在那条上，否则锚在命令本身之前
    scope = scope_id(event)
    window = (
        HistoryWindow.at_message(scope, reply.id)
        if reply
        else HistoryWindow.at_now(scope, msg_id)
    )
    if window and (context := window.recent(config.zssm_context_size)):
        user_prompt = (
            f"<type: context>\n{format_records(context)}\n</type: context>\n"
            f"{user_prompt}"
        )

    logger.info(f"最终用户提示: \n{user_prompt}")

    # 生成AI响应
    prompt = [user_prompt, *image_inputs] if image_inputs else user_prompt
    response = await generate_ai_response(system_prompt, prompt, tracker, window)
    # 如果失败，进行一次重试
    if response is None:
        logger.warning("AI 回复解析失败，正在重试...")
        response = await generate_ai_response(system_prompt, prompt, tracker, window)

    if response is None:
        return await UniMessage(Text("AI 回复解析失败, 请重试")).send(
            reply_to=Reply(msg_id)
        )

    await message_reaction("144", msg_id, event, bot)
    await send_answer(bot, event, response, tracker, window, reply_to=reply)
