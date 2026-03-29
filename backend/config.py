import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量配置
load_dotenv()

class Config:
    """系统全局配置类"""
    
    # 数据库连接 URL（用于状态、检查点持久化）
    # 默认回退使用本地的 SQLite 数据库用于开发调试
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    
    # Redis 连接 URL（用于异步任务队列与消息缓存）
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Node.js 代码重写引擎 (AST服务) 的访问地址
    REWRITE_ENGINE_URL = os.getenv("REWRITE_ENGINE_URL", "http://localhost:8080")
    
    # DeepSeek 大语言模型 API 密钥
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 导出单例配置对象供全局使用
config = Config()
