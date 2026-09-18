"""FastAPI应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from .config import settings
from .database import engine, Base
# 导入模型以确保create_all能识别到所有表
from .models import user, product, cart, order, chat


# 项目生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print(f"{settings.APP_NAME} 启动中...")
    print(f"数据库: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)
    print("数据库表初始化完成!")
    yield
    print(f"{settings.APP_NAME} 已关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置CORS(鉴权使用 Bearer Token, 不依赖 Cookie, 因此不开启 allow_credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ALLOW_ORIGINS],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=[settings.CORS_ALLOW_METHODS],
    allow_headers=[settings.CORS_ALLOW_HEADERS],
)


# 统一异常处理: 所有错误均返回 {code, message, data} 结构
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": message, "data": None},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    message = "请求参数校验失败"
    for err in exc.errors():
        msg = err.get("msg", "")
        # value_error 时, ctx.error 才是原始异常信息(如「手机号格式不正确」), 且不含前缀
        if err.get("type") == "value_error" and err.get("ctx", {}).get("error"):
            msg = str(err["ctx"]["error"])
        errors.append({"loc": err.get("loc"), "msg": msg})
        if message == "请求参数校验失败":
            message = msg
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": message, "data": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


# 注册API路由
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["根路径"], summary="root path")
def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["健康检查"], summary="health check")
def health_check():
    """健康检查"""
    return {"status": "healthy"}
