"""商品 Text2SQL 查询

流程: 自然语言问题 → LLM 生成 SQL(非流式、思考关闭、低温)
    → sqlglot AST 硬校验(仅单条 SELECT / 仅 products 表 / 自动 LIMIT)
    → 执行 → 行转 JSON 

安全约束(代码级, 不依赖提示词自觉): 
- 仅允许单条 SELECT 语句(UNION / 多语句 / 任何写操作 / INTO 均拒绝)
- 表白名单: 仅 products(含全部子查询层级, users / chat_* 等一律拒绝)
- LIMIT 缺失自动补 20, 超出 20 强制截断
"""
import re
from pathlib import Path
from typing import Any, Dict, List

import sqlglot
from sqlglot import exp
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.llm_client import chat_completion_sync, LLMError

# 提示词目录(自带加载缓存; 不直接依赖 chat_service 以避免循环导入)
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_prompt_cache: Dict[str, Any] = {}

# 允许查询的表白名单
ALLOWED_TABLES = {"products"}
# 单次查询返回行数上限
ROW_LIMIT = 20

_MARKDOWN_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.S | re.I)


def _load_sql_writer_prompt() -> str:
    """读取 SQL 生成器提示词(mtime 缓存, 改文件即生效)"""
    path = PROMPTS_DIR / "sql_writer.md"
    if not path.exists():
        raise RuntimeError(f"提示词文件缺失: {path}")
    mtime = path.stat().st_mtime
    cached = _prompt_cache.get("sql_writer")
    if not cached or cached["mtime"] != mtime:
        _prompt_cache["sql_writer"] = {"mtime": mtime, "text": path.read_text(encoding="utf-8").strip()}
    return _prompt_cache["sql_writer"]["text"]


def _strip_markdown_fence(raw: str) -> str:
    """剥离模型可能顺手加上的 Markdown 代码块包裹"""
    match = _MARKDOWN_FENCE_RE.search(raw)
    sql = match.group(1) if match else raw
    return sql.strip().rstrip(";").strip()


def _check_limit(tree: exp.Select) -> None:
    """LIMIT 缺失自动补 ROW_LIMIT, 超出上限强制截断"""
    limit_expr = tree.args.get("limit")
    if limit_expr is not None:
        try:
            current = int(limit_expr.expression.this)
            if current <= ROW_LIMIT:
                return
        except (AttributeError, ValueError, TypeError):
            pass
    # Select.limit() 返回新树而非原地修改, 必须用 set 写回
    tree.set("limit", exp.Limit(expression=exp.Literal.number(ROW_LIMIT)))


def validate_and_rewrite(sql: str) -> str:
    """AST 级安全校验与改写, 返回可安全执行的 SQL; 不合法时抛 HTTPException(400)"""
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except sqlglot.errors.ParseError as e:
        raise HTTPException(status_code=400, detail=f"生成的 SQL 无法解析: {e}")

    if len(statements) != 1:
        raise HTTPException(status_code=400, detail="只允许一条 SELECT 查询语句")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise HTTPException(status_code=400, detail="只允许 SELECT 查询语句")
    if tree.args.get("into"):
        raise HTTPException(status_code=400, detail="不允许 INTO 子句")

    tables = {t.name.lower() for t in tree.find_all(exp.Table)}
    forbidden = tables - ALLOWED_TABLES
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail=f"不允许查询这些表: {', '.join(sorted(forbidden))}(仅允许 products)",
        )

    _check_limit(tree)
    return tree.sql(dialect="mysql")


def run_product_query(db: Session, question: str) -> Dict[str, Any]:
    """统一商品查询入口: LLM 写 SQL → 校验改写 → 执行 

    成功返回 {"rows": [...], "count": n}; 失败抛 HTTPException(400), 
    由 registry.execute_tool 统一兜底为 {ok: False, error} 回传主模型 
    """
    if not question.strip():
        raise HTTPException(status_code=400, detail="请描述要查询的商品条件")

    # 1. LLM 生成 SQL(非流式、思考关闭、低温)
    try:
        raw_sql = chat_completion_sync(
            messages=[
                {"role": "system", "content": _load_sql_writer_prompt()},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            thinking=False,
        )
    except LLMError as e:
        raise HTTPException(status_code=400, detail=f"SQL 生成失败: {e}")

    # 2. AST 校验与改写
    safe_sql = validate_and_rewrite(_strip_markdown_fence(raw_sql))

    # 3. 执行并转为可序列化行(Decimal/datetime 交给 json.dumps 的 default=str 兜底)
    try:
        result = db.execute(text(safe_sql))
        rows: List[Dict[str, Any]] = [dict(m) for m in result.mappings().all()][:ROW_LIMIT]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询执行失败: {e}")

    return {"rows": rows, "count": len(rows)}
