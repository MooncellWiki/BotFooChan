"""LLM：服务商、模型、模型路由、提示词。

服务商和模型存在配置段 ``llm`` 里；「路由」是各配置段里标了 ``model_ref`` 的字段
（chat.model、zssm.zssm_ai_model……），「提示词」是标了 ``prompt`` 的字段，
改的都是对应配置段，见 :mod:`src.providers.settings`。
"""

from datetime import datetime
import time
from typing import Annotated, Any, Literal, get_args

from fastapi import APIRouter, Body
import httpx
from pydantic import BaseModel, Field
from pydantic_ai.settings import ModelSettings

from src.plugins.webui.auth import CurrentAdmin
from src.providers import settings
from src.providers.llm import ApiType, ModelEndpoint, create_agent, llm_config
from src.providers.llm.config import LLMModel
from src.providers.settings.fields import flagged

from .common import actor, aware, conflict, not_found
from .settings_api import get_or_404, save_section

router = APIRouter(prefix="/llm", tags=["llm"])

API_TYPES: list[str] = list(get_args(ApiType))


class ProviderOut(BaseModel):
    name: str
    base_url: str
    api_key: str | None
    """打码后的 Key；原样提交回来表示不改"""
    api_type: ApiType | None
    vision: bool | None
    proxy: str | None
    models: list[str]
    """用到这个服务商的模型别名"""


class ModelOut(BaseModel):
    alias: str
    provider: str
    name: str
    api_type: ApiType | None
    vision: bool | None
    resolved_api_type: ApiType | None
    """实际走的协议（服务商不存在时为 None）"""
    supports_vision: bool | None
    routes: list[str]
    """引用了这个别名的路由（配置段.字段）"""


class LLMOverview(BaseModel):
    providers: list[ProviderOut]
    models: list[ModelOut]
    api_types: list[str]


class Route(BaseModel):
    id: str
    """配置段.字段"""
    section: str
    section_title: str
    field: str
    description: str
    value: str | None
    status: Literal["ok", "unset", "missing", "no_provider", "no_key"]
    detail: str


def _endpoint_of(model: LLMModel) -> ModelEndpoint | None:
    provider = llm_config.providers.get(model.provider)
    if provider is None:
        return None
    return ModelEndpoint(
        name=model.name,
        base_url=provider.base_url,
        api_key=provider.api_key,
        api_type=model.api_type or provider.api_type,
        vision=model.vision if model.vision is not None else provider.vision,
        proxy=provider.proxy,
    )


def _check_ref(ref: str | None) -> tuple[str, str]:
    """(状态, 说明)，和 resolve_endpoint 的判断一致，但不打日志"""
    if not ref:
        return "unset", "没有配置"
    model = llm_config.models.get(ref)
    if model is None:
        if ":" not in ref:
            return "missing", f"模型注册表里没有 {ref}"
        provider_name, _, name = ref.partition(":")
        model = LLMModel(provider=provider_name, name=name)
    provider = llm_config.providers.get(model.provider)
    if provider is None:
        return "no_provider", f"服务商 {model.provider} 不存在"
    if not provider.api_key:
        return "no_key", f"服务商 {model.provider} 没有配置 API Key"
    return "ok", f"{model.provider} / {model.name}"


def routes() -> list[Route]:
    out: list[Route] = []
    for section in settings.sections():
        for field in flagged(section.model, "model_ref"):
            value = getattr(section.value, field)
            status, detail = _check_ref(value)
            info = section.model.model_fields[field]
            out.append(
                Route(
                    id=f"{section.key}.{field}",
                    section=section.key,
                    section_title=section.title,
                    field=field,
                    description=info.description or "",
                    value=value,
                    status=status,  # pyright: ignore[reportArgumentType]
                    detail=detail,
                )
            )
    return out


def _overview() -> LLMOverview:
    masked = settings.get_section("llm").masked()
    route_list = routes()
    providers = [
        ProviderOut(
            name=name,
            base_url=p.base_url,
            api_key=masked["providers"][name].get("api_key"),
            api_type=p.api_type,
            vision=p.vision,
            proxy=p.proxy,
            models=[a for a, m in llm_config.models.items() if m.provider == name],
        )
        for name, p in llm_config.providers.items()
    ]
    models: list[ModelOut] = []
    for alias, m in llm_config.models.items():
        endpoint = _endpoint_of(m)
        models.append(
            ModelOut(
                alias=alias,
                provider=m.provider,
                name=m.name,
                api_type=m.api_type,
                vision=m.vision,
                resolved_api_type=endpoint.resolved_api_type if endpoint else None,
                supports_vision=endpoint.supports_vision if endpoint else None,
                routes=[r.id for r in route_list if r.value == alias],
            )
        )
    return LLMOverview(providers=providers, models=models, api_types=API_TYPES)


async def _save_llm(data: dict[str, Any], admin_actor: str) -> LLMOverview:
    await save_section("llm", data, admin_actor)
    return _overview()


@router.get("")
async def get_llm() -> LLMOverview:
    """服务商和模型"""
    return _overview()


class ProviderIn(BaseModel):
    base_url: str
    api_key: str | None = None
    """打码值表示不改；空串或 null 表示清掉"""
    api_type: ApiType | None = None
    vision: bool | None = None
    proxy: str | None = None


@router.put("/providers/{name}")
async def put_provider(name: str, body: ProviderIn, admin: CurrentAdmin) -> LLMOverview:
    """新增或修改服务商"""
    data = settings.get_section("llm").masked()
    data["providers"][name] = body.model_dump()
    return await _save_llm(data, actor(admin))


@router.delete("/providers/{name}")
async def delete_provider(name: str, admin: CurrentAdmin) -> LLMOverview:
    """删除服务商（还有模型引用它时不让删）"""
    data = settings.get_section("llm").masked()
    if name not in data["providers"]:
        raise not_found(f"服务商 {name} ")
    if users := [a for a, m in llm_config.models.items() if m.provider == name]:
        raise conflict(f"这些模型还在用它：{'、'.join(users)}")
    del data["providers"][name]
    return await _save_llm(data, actor(admin))


class ModelIn(BaseModel):
    provider: str
    name: str
    api_type: ApiType | None = None
    vision: bool | None = None


@router.put("/models/{alias}")
async def put_model(alias: str, body: ModelIn, admin: CurrentAdmin) -> LLMOverview:
    """新增或修改模型别名"""
    if body.provider not in llm_config.providers:
        raise not_found(f"服务商 {body.provider} ")
    data = settings.get_section("llm").masked()
    data["models"][alias] = body.model_dump()
    return await _save_llm(data, actor(admin))


@router.delete("/models/{alias}")
async def delete_model(alias: str, admin: CurrentAdmin) -> LLMOverview:
    """删除模型别名（还有路由引用它时不让删）"""
    data = settings.get_section("llm").masked()
    if alias not in data["models"]:
        raise not_found(f"模型 {alias} ")
    if users := [r.id for r in routes() if r.value == alias]:
        raise conflict(f"这些功能还在用它：{'、'.join(users)}")
    del data["models"][alias]
    return await _save_llm(data, actor(admin))


class ModelTestResult(BaseModel):
    ok: bool
    latency_ms: int
    output: str = ""
    error: str = ""


@router.post("/models/{alias}/test")
async def test_model(alias: str) -> ModelTestResult:
    """用这个模型发一句话，看通不通"""
    if (model := llm_config.models.get(alias)) is None:
        raise not_found(f"模型 {alias} ")
    if (endpoint := _endpoint_of(model)) is None:
        return ModelTestResult(ok=False, latency_ms=0, error="服务商不存在")
    endpoint = endpoint.model_copy(update={"alias": alias, "provider": model.provider})
    agent = create_agent(
        endpoint, settings=ModelSettings(timeout=30, max_tokens=64), task="webui_test"
    )
    started = time.perf_counter()
    try:
        result = await agent.run("只回复两个字：在的")
    except Exception as e:
        return ModelTestResult(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=f"{type(e).__name__}: {e}"[:2000],
        )
    return ModelTestResult(
        ok=True,
        latency_ms=int((time.perf_counter() - started) * 1000),
        output=str(result.output)[:500],
    )


class RemoteModels(BaseModel):
    models: list[str] = Field(default_factory=list)
    error: str = ""


@router.post("/providers/{name}/remote-models")
async def list_remote_models(name: str) -> RemoteModels:
    """向服务商查它有哪些模型（OpenAI 的 /models 或 Anthropic 的 /v1/models）"""
    if (provider := llm_config.providers.get(name)) is None:
        raise not_found(f"服务商 {name} ")
    if not provider.api_key:
        return RemoteModels(error="没有配置 API Key")
    probe = ModelEndpoint(
        name="", base_url=provider.base_url, api_type=provider.api_type
    )
    if probe.resolved_api_type == "anthropic":
        url = probe.resolved_base_url.rstrip("/") + "/v1/models"
        headers = {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01"}
    else:
        url = provider.base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {provider.api_key}"}
    try:
        async with httpx.AsyncClient(timeout=20, proxy=provider.proxy) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            items = response.json().get("data") or []
    except Exception as e:
        return RemoteModels(error=f"{type(e).__name__}: {e}"[:500])
    return RemoteModels(
        models=sorted(str(i.get("id")) for i in items if isinstance(i, dict))
    )


@router.get("/routes")
async def list_routes() -> list[Route]:
    """各功能用的模型"""
    return routes()


class RouteIn(BaseModel):
    model: str | None


@router.put("/routes/{section}/{field}")
async def put_route(
    section: str, field: str, body: RouteIn, admin: CurrentAdmin
) -> list[Route]:
    """改某个功能用的模型"""
    sec = get_or_404(section)
    if field not in flagged(sec.model, "model_ref"):
        raise not_found(f"路由 {section}.{field} ")
    data = sec.masked()
    data[field] = body.model or None
    await save_section(section, data, actor(admin))
    return routes()


class Prompt(BaseModel):
    id: str
    section: str
    section_title: str
    field: str
    description: str
    value: str
    updated_at: datetime | None


def _prompts() -> list[Prompt]:
    out: list[Prompt] = []
    for section in settings.sections():
        for field in flagged(section.model, "prompt"):
            out.append(
                Prompt(
                    id=f"{section.key}.{field}",
                    section=section.key,
                    section_title=section.title,
                    field=field,
                    description=section.model.model_fields[field].description or "",
                    value=getattr(section.value, field) or "",
                    updated_at=aware(section.updated_at)
                    if section.updated_at
                    else None,
                )
            )
    return out


@router.get("/prompts")
async def list_prompts() -> list[Prompt]:
    """可以在后台改的提示词"""
    return _prompts()


@router.put("/prompts/{section}/{field}")
async def put_prompt(
    section: str,
    field: str,
    value: Annotated[str, Body(embed=True)],
    admin: CurrentAdmin,
) -> list[Prompt]:
    """改提示词"""
    sec = get_or_404(section)
    if field not in flagged(sec.model, "prompt"):
        raise not_found(f"提示词 {section}.{field} ")
    data = sec.masked()
    data[field] = value
    await save_section(section, data, actor(admin))
    return _prompts()
