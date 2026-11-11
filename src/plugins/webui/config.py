from nonebot import get_driver, get_plugin_config
from nonebot.adapters.github.config import GitHubApp, OAuthApp
from pydantic import BaseModel, Field, field_validator

BASE_PATH = "/admin"
"""前端页面挂载的路径"""
API_PATH = f"{BASE_PATH}/api"
"""接口挂载的路径"""


class ScopedConfig(BaseModel):
    secret_key: str = ""
    """签登录 cookie 的密钥，之后也用来加密存进库里的 API Key。

    不配时 WebUI 不启用；ENVIRONMENT=dev 下会临时生成一个，重启后要重新登录
    """
    public_url: str = ""
    """对外访问地址（如 ``https://bot.example.com``）。

    用来拼 GitHub OAuth 的回调地址、决定 cookie 加不加 Secure；留空时取请求本身的
    地址，而 Caddy 后面看到的是内网 http，所以生产环境要配
    """
    admins: set[str] = Field(default_factory=set)
    """允许登录的 GitHub 用户名，不区分大小写"""
    github_client_id: str = ""
    github_client_secret: str = ""
    """GitHub OAuth 凭据。

    留空时用 GITHUB_APPS 里第一个带 client_id / client_secret 的应用
    """
    dev_admin: str = ""
    """仅 ENVIRONMENT=dev 生效：不用登录，直接当作这个 GitHub 用户"""
    session_days: int = Field(default=7, gt=0)
    """登录有效期（天）"""
    dist: str = "web/.output/public"
    """前端构建产物所在目录"""

    @field_validator(
        "secret_key",
        "public_url",
        "github_client_id",
        "github_client_secret",
        "dev_admin",
        mode="before",
    )
    @classmethod
    def _empty_when_unset(cls, value: object) -> object:
        # .env 里只写键名不写值表示「不配置」，取到的是 None
        return "" if value is None else value

    @field_validator("admins", mode="before")
    @classmethod
    def _empty_set_when_unset(cls, value: object) -> object:
        return set() if value is None or value == "" else value

    @field_validator("public_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("admins")
    @classmethod
    def _normalize_logins(cls, value: set[str]) -> set[str]:
        return {login.strip().lower() for login in value if login.strip()}

    @field_validator("dev_admin")
    @classmethod
    def _normalize_login(cls, value: str) -> str:
        return value.strip().lower()


class Config(BaseModel):
    webui: ScopedConfig = Field(default_factory=ScopedConfig)
    """WebUI Config"""
    github_apps: list[GitHubApp | OAuthApp] = Field(default_factory=list)
    """GitHub 适配器的应用列表，没单独配 OAuth 凭据时借它的"""


plugin_config = get_plugin_config(Config)
webui_config = plugin_config.webui


def is_dev() -> bool:
    return get_driver().env == "dev"


def dev_admin() -> str | None:
    """开发模式下免登录的用户名；不是开发模式或没配时为 None"""
    return webui_config.dev_admin if is_dev() and webui_config.dev_admin else None


def oauth_credentials() -> tuple[str, str] | None:
    """GitHub OAuth 的 (client_id, client_secret)"""
    if webui_config.github_client_id and webui_config.github_client_secret:
        return webui_config.github_client_id, webui_config.github_client_secret
    for app in plugin_config.github_apps:
        if app.client_id and app.client_secret:
            return app.client_id, app.client_secret
    return None
