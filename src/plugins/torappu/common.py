import json
from typing import Any

from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna

from .data_source import (
    filter_bundles,
    get_bundle,
    get_health,
    get_item_demand,
    get_manifest_detail,
    get_version_detail,
    list_files,
    list_manifest_children,
    list_versions,
    search_files,
    search_manifest,
)
from .utils import call_api, find_version, format_size, resolve_version

MAX_RESULTS = 10

status_cmd = on_alconna(
    Alconna("torappu_status"),
    aliases={"torappu状态"},
    priority=10,
    use_cmd_start=True,
)

version_cmd = on_alconna(
    Alconna("torappu_version", Args["version?", str]),
    aliases={"torappu版本"},
    priority=10,
    use_cmd_start=True,
)

search_cmd = on_alconna(
    Alconna("torappu_search", Args["keyword?", str]["version?", str]),
    aliases={"torappu搜索"},
    priority=10,
    use_cmd_start=True,
)

detail_cmd = on_alconna(
    Alconna("torappu_detail", Args["asset?", str]["version?", str]),
    aliases={"torappu详情"},
    priority=10,
    use_cmd_start=True,
)

dir_cmd = on_alconna(
    Alconna("torappu_dir", Args["directory?", str]["version?", str]),
    aliases={"torappu目录"},
    priority=10,
    use_cmd_start=True,
)

files_cmd = on_alconna(
    Alconna("torappu_files", Args["keyword?", str]),
    aliases={"torappu文件"},
    priority=10,
    use_cmd_start=True,
)

bundle_cmd = on_alconna(
    Alconna("torappu_bundle", Args["query?", str]["version?", str]),
    aliases={"torappu包"},
    priority=10,
    use_cmd_start=True,
)

item_cmd = on_alconna(
    Alconna("torappu_item", Args["item?", str]),
    aliases={"材料需求"},
    priority=10,
    use_cmd_start=True,
)


@status_cmd.handle()
async def handle_status() -> None:
    health = await call_api(status_cmd, get_health())
    versions = await call_api(status_cmd, list_versions())

    lines = [
        f"torappu 服务状态：{'正常' if health.get('ok') else '异常'}",
        f"版本总数：{len(versions)}",
    ]
    if versions:
        latest = versions[-1]
        lines.append(f"最新版本：{latest['clientVersion']} / {latest['resVersion']}")
        lines.append(
            f"资源就绪：{'是' if latest['isReady'] else '否'}"
            f"（资源映射：{latest['assetMappingStatus']}）"
        )
    await status_cmd.finish("\n".join(lines))


@version_cmd.handle()
async def handle_version(version: Match[str]) -> None:
    versions = await call_api(version_cmd, list_versions())
    if not versions:
        await version_cmd.finish("版本列表为空")

    if not version.available:
        lines = [f"最近 {min(len(versions), MAX_RESULTS)} 个版本："]
        for v in reversed(versions[-MAX_RESULTS:]):
            ready = "✅" if v["isReady"] else "⏳"
            lines.append(
                f"{ready} #{v['id']} {v['clientVersion']} / {v['resVersion']}"
                f"（映射：{v['assetMappingStatus']}）"
            )
        await version_cmd.finish("\n".join(lines))

    index = find_version(versions, version.result)
    if index is None:
        await version_cmd.finish(f"未找到版本：{version.result}")

    summary = versions[index]
    detail = await call_api(version_cmd, get_version_detail(summary["id"]))

    lines = [
        f"版本 #{detail['id']}",
        f"客户端版本：{detail['clientVersion']}",
        f"资源版本：{detail['resVersion']}",
        f"资源就绪：{'是' if detail['isReady'] else '否'}"
        f"（资源映射：{summary['assetMappingStatus']}）",
    ]
    try:
        hot_update = json.loads(detail["hotUpdateList"])
    except json.JSONDecodeError, TypeError:
        hot_update = {}
    if ab_infos := hot_update.get("abInfos"):
        total_size = sum(info.get("totalSize", 0) for info in ab_infos)
        lines.append(f"资源包数量：{len(ab_infos)}")
        lines.append(f"资源总大小：{format_size(total_size)}")
    await version_cmd.finish("\n".join(lines))


@search_cmd.handle()
async def handle_search(keyword: Match[str], version: Match[str]) -> None:
    if not keyword.available:
        await search_cmd.finish("用法：/torappu搜索 <关键词> [版本]")

    ver = await resolve_version(
        search_cmd, version.result if version.available else None
    )
    results = await call_api(search_cmd, search_manifest(ver["id"], keyword.result))
    if not results:
        await search_cmd.finish(f"版本 {ver['resVersion']} 中未找到：{keyword.result}")

    lines = [f"版本 {ver['resVersion']} 搜索结果（共 {len(results)} 条）："]
    for node in results[:MAX_RESULTS]:
        suffix = "/" if node["nodeType"] != "file" else ""
        lines.append(f"{node['path']}{suffix}")
    if len(results) > MAX_RESULTS:
        lines.append(f"……仅显示前 {MAX_RESULTS} 条")
    await search_cmd.finish("\n".join(lines))


@detail_cmd.handle()
async def handle_detail(asset: Match[str], version: Match[str]) -> None:
    if not asset.available:
        await detail_cmd.finish(
            "用法：/torappu详情 <资源完整路径> [版本]\n资源路径可通过 /torappu搜索 获取"
        )

    ver = await resolve_version(
        detail_cmd, version.result if version.available else None
    )
    detail = await call_api(detail_cmd, get_manifest_detail(ver["id"], asset.result))

    lines = [f"资源：{detail['assetName']}", f"版本：{ver['resVersion']}"]
    if short_name := detail.get("shortName"):
        lines.append(f"短名称：{short_name}")
    if asset_path := detail.get("assetPath"):
        lines.append(f"资源路径：{asset_path}")
    lines.append(f"所属 bundle：{detail['bundlePath']}")
    if bundle_size := detail.get("bundleSize"):
        lines.append(f"bundle 大小：{format_size(bundle_size)}")
    if bundle_hash := detail.get("bundleHash"):
        lines.append(f"bundle 哈希：{bundle_hash}")
    await detail_cmd.finish("\n".join(lines))


@dir_cmd.handle()
async def handle_dir(directory: Match[str], version: Match[str]) -> None:
    ver = await resolve_version(dir_cmd, version.result if version.available else None)
    target = directory.result if directory.available else None
    children = await call_api(dir_cmd, list_manifest_children(ver["id"], target))
    if not children:
        await dir_cmd.finish(f"目录 {target or '/'} 为空")

    lines = [
        f"版本 {ver['resVersion']} 目录 {target or '/'}（共 {len(children)} 项）："
    ]
    for node in children[:MAX_RESULTS]:
        suffix = "/" if node["nodeType"] != "file" else ""
        lines.append(f"{node['name']}{suffix}")
    if len(children) > MAX_RESULTS:
        lines.append(f"……仅显示前 {MAX_RESULTS} 项")
    await dir_cmd.finish("\n".join(lines))


@files_cmd.handle()
async def handle_files(keyword: Match[str]) -> None:
    if not keyword.available:
        await files_cmd.finish(
            "用法：/torappu文件 <关键词>（搜索）或 /torappu文件 <目录路径>/（列目录）"
        )

    if keyword.result.endswith("/"):
        listing = await call_api(files_cmd, list_files(keyword.result.rstrip("/")))
        children = listing.get("children", [])
        lines = [f"目录 {listing['dir']['path']}（共 {len(children)} 项）："]
        for child in children[:MAX_RESULTS]:
            if child["is_dir"]:
                lines.append(f"{child['name']}/")
            else:
                lines.append(f"{child['name']}（{format_size(child['size'])}）")
        if len(children) > MAX_RESULTS:
            lines.append(f"……仅显示前 {MAX_RESULTS} 项")
        await files_cmd.finish("\n".join(lines))

    results = await call_api(files_cmd, search_files(keyword.result))
    if not results:
        await files_cmd.finish(f"未找到文件：{keyword.result}")

    lines = [f"文件搜索结果（共 {len(results)} 条）："]
    for file in results[:MAX_RESULTS]:
        suffix = "/" if file["is_dir"] else f"（{format_size(file['size'])}）"
        lines.append(f"{file['path']}{suffix}")
    if len(results) > MAX_RESULTS:
        lines.append(f"……仅显示前 {MAX_RESULTS} 条")
    await files_cmd.finish("\n".join(lines))


def _format_bundle(bundle: dict[str, Any]) -> str:
    return (
        f"版本 #{bundle['versionId']} {bundle['versionRes']}\n"
        f"大小：{format_size(bundle['fileSize'])}\n"
        f"哈希:{bundle['fileHash'][:16]}…"
    )


@bundle_cmd.handle()
async def handle_bundle(query: Match[str], version: Match[str]) -> None:
    if not query.available:
        await bundle_cmd.finish("用法：/torappu包 <bundle路径|ID> [版本]")

    if query.result.isdigit():
        bundle = await call_api(bundle_cmd, get_bundle(int(query.result)))
        await bundle_cmd.finish(f"bundle：{bundle['path']}\n{_format_bundle(bundle)}")

    version_id = None
    if version.available:
        ver = await resolve_version(bundle_cmd, version.result)
        version_id = ver["id"]
    bundles = await call_api(
        bundle_cmd, filter_bundles(path=query.result, version_id=version_id)
    )
    if not bundles:
        await bundle_cmd.finish(f"未找到 bundle：{query.result}")

    bundles.sort(key=lambda bundle: bundle["versionId"], reverse=True)
    lines = [f"bundle：{query.result}（共 {len(bundles)} 条记录）"]
    lines.extend(_format_bundle(bundle) for bundle in bundles[:5])
    if len(bundles) > 5:
        lines.append("……仅显示最近 5 条")
    await bundle_cmd.finish("\n".join(lines))


@item_cmd.handle()
async def handle_item(item: Match[str]) -> None:
    if not item.available:
        await item_cmd.finish("用法：/材料需求 <道具名>")

    demand = await call_api(item_cmd, get_item_demand(item.result))
    if not demand:
        await item_cmd.finish(f"暂无 {item.result} 的需求数据")

    def char_total(info: dict[str, Any]) -> int:
        return (
            info.get("elite", 0)
            + info.get("skill", 0)
            + sum(info.get("mastery", []))
            + info.get("uniequip", 0)
        )

    lines = [
        f"{item.result} 需求统计（共 {len(demand)} 名干员）：",
        f"精英化：{sum(info.get('elite', 0) for info in demand.values())}",
        f"技能升级：{sum(info.get('skill', 0) for info in demand.values())}",
        f"技能专精：{sum(sum(info.get('mastery', [])) for info in demand.values())}",
        f"模组：{sum(info.get('uniequip', 0) for info in demand.values())}",
        "需求最高：",
    ]
    top_chars = sorted(demand.values(), key=char_total, reverse=True)[:5]
    lines.extend(
        f"{info.get('name', '未知')}（{info.get('rarity', '?')}★）：{char_total(info)}"
        for info in top_chars
    )
    await item_cmd.finish("\n".join(lines))
