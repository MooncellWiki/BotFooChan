from nonebot import on_command
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me

from .add_cookie import do_add_cookie
from .add_cookie_target import do_add_cookie_target
from .add_sub import do_add_sub
from .del_cookie import do_del_cookie
from .del_cookie_target import do_del_cookie_target
from .del_sub import do_del_sub
from .query_sub import do_query_sub
from .utils import (
    admin_permission,
    common_platform,
    configurable_to_me,
    set_target_user_info,
)

add_sub_matcher = on_command(
    "添加订阅",
    rule=configurable_to_me,
    permission=admin_permission(),
    priority=5,
    block=True,
)
add_sub_matcher.handle()(set_target_user_info)
do_add_sub(add_sub_matcher)


query_sub_matcher = on_command(
    "查询订阅", rule=configurable_to_me, priority=5, block=True
)
query_sub_matcher.handle()(set_target_user_info)
do_query_sub(query_sub_matcher)


del_sub_matcher = on_command(
    "删除订阅",
    rule=configurable_to_me,
    permission=admin_permission(),
    priority=5,
    block=True,
)
del_sub_matcher.handle()(set_target_user_info)
do_del_sub(del_sub_matcher)

add_cookie_matcher = on_command(
    "添加cookie",
    aliases={"添加Cookie"},
    rule=to_me(),
    permission=SUPERUSER,
    priority=5,
    block=True,
)
do_add_cookie(add_cookie_matcher)

add_cookie_target_matcher = on_command(
    "关联cookie",
    aliases={"关联Cookie"},
    rule=to_me(),
    permission=SUPERUSER,
    priority=5,
    block=True,
)
do_add_cookie_target(add_cookie_target_matcher)

del_cookie_target_matcher = on_command(
    "取消关联cookie",
    aliases={"取消关联Cookie"},
    rule=to_me(),
    permission=SUPERUSER,
    priority=5,
    block=True,
)
do_del_cookie_target(del_cookie_target_matcher)

del_cookie_matcher = on_command(
    "删除cookie",
    aliases={"删除Cookie"},
    rule=to_me(),
    permission=SUPERUSER,
    priority=5,
    block=True,
)
do_del_cookie(del_cookie_matcher)

no_permission_matcher = on_command(
    "添加订阅",
    rule=configurable_to_me,
    # 没有搬 web 后台，所以不含“管理后台”
    aliases={
        "删除订阅",
        "添加cookie",
        "删除cookie",
        "关联cookie",
        "取消关联cookie",
    },
    priority=8,
    block=True,
)


@no_permission_matcher.handle()
async def send_no_permission():
    await no_permission_matcher.finish("您没有权限进行此操作，请联系 Bot 管理员")


__all__ = [
    "add_cookie_matcher",
    "add_cookie_target_matcher",
    "add_sub_matcher",
    "common_platform",
    "del_cookie_matcher",
    "del_cookie_target_matcher",
    "del_sub_matcher",
    "no_permission_matcher",
    "query_sub_matcher",
]
