from typing import Any
from urllib.parse import quote

import httpx

from .config import plugin_config


def _api_url(path: str) -> httpx.URL:
    return httpx.URL(plugin_config.torappu_api_url).join(path)


async def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_api_url(path), params=params)
    resp.raise_for_status()
    return resp.json()


async def get_health() -> dict[str, Any]:
    return await _get_json("/api/v1/_health")


async def list_versions() -> list[dict[str, Any]]:
    return await _get_json("/api/v1/version")


async def get_version_detail(version_id: int) -> dict[str, Any]:
    return await _get_json(f"/api/v1/version/{version_id}")


async def search_manifest(version_id: int, keyword: str) -> list[dict[str, Any]]:
    return await _get_json(
        f"/api/v1/manifest/{version_id}/search", params={"q": keyword}
    )


async def get_manifest_detail(version_id: int, asset_name: str) -> dict[str, Any]:
    return await _get_json(
        f"/api/v1/manifest/{version_id}/detail", params={"asset_name": asset_name}
    )


async def list_manifest_children(
    version_id: int, directory: str | None = None
) -> list[dict[str, Any]]:
    params = {"dir": directory} if directory else None
    return await _get_json(f"/api/v1/manifest/{version_id}/children", params=params)


async def search_files(keyword: str) -> list[dict[str, Any]]:
    return await _get_json("/api/v1/files", params={"path": keyword})


async def list_files(path: str) -> dict[str, Any]:
    return await _get_json(f"/api/v1/files/{quote(path, safe='')}")


async def get_item_demand(item_name: str) -> dict[str, Any]:
    return await _get_json(f"/api/v1/item/{quote(item_name, safe='')}/demand")


async def filter_bundles(
    path: str | None = None, version_id: int | None = None
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if path is not None:
        params["path"] = path
    if version_id is not None:
        params["version"] = version_id
    return await _get_json("/api/v1/bundle", params=params)


async def get_bundle(bundle_id: int) -> dict[str, Any]:
    return await _get_json(f"/api/v1/bundle/{bundle_id}")


async def launch_container(
    client_version: str,
    res_version: str,
    prev_client_version: str,
    prev_res_version: str,
    include: str | None = None,
    exclude: str | None = None,
) -> dict[str, Any]:
    payload = {
        "client_version": client_version,
        "res_version": res_version,
        "prev_client_version": prev_client_version,
        "prev_res_version": prev_res_version,
        "include": include,
        "exclude": exclude,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            _api_url("/api/v1/docker/launch"),
            headers={"torappu-auth": plugin_config.torappu_auth_token or ""},
            json=payload,
        )
    resp.raise_for_status()
    return resp.json()
