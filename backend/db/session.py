from .models import SessionLocal

def get_db():
    """
    FastAPI 依赖注入 (Dependency Injection) 的数据库会话生成器。
    在处理每个 HTTP 请求时，创建一个新的数据库会话，
    并在请求结束时（无论成功或异常）自动关闭会话，防止数据库连接泄露。
    """
    db = SessionLocal()
    try:
        # yield 将会话对象交给具体的路由处理函数使用
        yield db
    finally:
        # 确保在处理结束后释放连接池资源
        db.close()