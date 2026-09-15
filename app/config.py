from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus

# 项目配置
class Settings(BaseSettings):

    # FastAPI配置
    APP_NAME: str = "购物车管理系统"
    APP_DESCRIPTION: str = "基于FastAPI开发的购物车管理系统"
    APP_VERSION: str = "2.0"
    DEBUG: bool = True

    # 数据库配置(BaseSettings自动读取.env)
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str

    # 连接池配置
    POOL_SIZE: int
    MAX_OVERFLOW: int
    POOL_TIMEOUT: int
    POOL_RECYCLE: int

    # JWT配置（SECRET_KEY 必须通过 .env 或环境变量提供，禁止使用默认值）
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # DeepSeek LLM 配置（智能客服；DEEPSEEK_API_KEY 为空时客服功能自动停用）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TEMPERATURE: float = 0.7
    DEEPSEEK_MAX_TOKENS: int = 2048
    DEEPSEEK_TOP_P: float = 0.95
    # 思考模式开关：显式写入请求参数 thinking.type（V4 系列服务端默认 enabled，必须显式覆盖）
    DEEPSEEK_THINKING: bool = False

    # Docker 部署专用（由 docker-compose.yml 读取，后端运行时不使用；声明以保持 .env 严格校验通过）
    MYSQL_ROOT_PASSWORD: str = ""
    FRONTEND_PORT: int = 80
    UVICORN_WORKERS: int = 2

    @property
    def LLM_ENABLED(self) -> bool:
        """智能客服是否可用"""
        return bool(self.DEEPSEEK_API_KEY.strip())

    # CORS配置
    CORS_ALLOW_ORIGINS: str
    CORS_ALLOW_CREDENTIALS: bool
    CORS_ALLOW_METHODS: str
    CORS_ALLOW_HEADERS: str

    # 动态拼接数据库连接url（对用户名/密码做 URL 编码，避免特殊字符破坏连接串）
    @property
    def DATABASE_URL(self) -> str:
        user = quote_plus(self.DATABASE_USER)
        password = quote_plus(self.DATABASE_PASSWORD)
        return f"mysql+pymysql://{user}:{password}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}?charset=utf8"

    # 读取.env
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()

settings = get_settings()