from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from openai import OpenAI

from . import config

client = OpenAI(
    base_url=config.llm_base_url,
    api_key=config.llm_api_key,
)

llm_chat = on_command(
    "llm_chat",
    aliases={"ds"},
    block=True,
)


@llm_chat.handle()
async def handle_llm_chat(args: Message = CommandArg()):
    if question := args.extract_plain_text():
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://mooncell.wiki",
                "X-Title": "Mooncell",
            },
            extra_body={},
            model=config.llm_model,
            messages=[{"role": "user", "content": question}],
        )
        await llm_chat.finish(completion.choices[0].message.content)
    else:
        await llm_chat.finish("请输入问题")
