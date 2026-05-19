from __future__ import annotations

from collections.abc import Generator
from sqlmodel import Session, SQLModel, create_engine
from app.core.config import settings
from app.utils.string_tools import build_database_url


# 创建数据库的客户端连接对象 create_engine
# 创建数据库的客户端会话对象 Session
# 创建数据库的客户端基础类 SQLModel

def build_engine():
    """构建数据库引擎。

    Returns:
        Engine: 基于当前配置创建的 SQLModel/SQLAlchemy 引擎实例。
    """
    
    database_url = build_database_url(
        db_engine=settings.db_engine,
        db_driver=settings.db_driver,
        db_host=settings.db_host,
        db_port=settings.db_port,
        db_name=settings.db_name,
        db_user=settings.db_user,
        db_password=settings.db_password,
        db_sqlite_path=settings.db_sqlite_path,
    )
    # 根据数据库类型动态设置连接参数，专门针对 SQLite 做线程限制的放宽处理
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, echo=False, connect_args=connect_args)


engine = build_engine()

def create_db_and_tables() -> None:
    """根据当前 SQLModel 元数据创建数据库表。"""
    SQLModel.metadata.create_all(engine)


def drop_db_and_tables() -> None:
    """根据当前 SQLModel 元数据创建数据库表。"""
    SQLModel.metadata.drop_all(engine)


def get_session() -> Generator[Session, None, None]:
    """提供数据库会话依赖。

    Yields:
        Session: 当前请求可复用的 SQLModel 会话对象。
    """
    with Session(engine) as session:
        yield session
