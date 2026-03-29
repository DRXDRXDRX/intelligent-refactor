from sqlalchemy import Column, String, Float, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import config

# 创建 SQLAlchemy 声明式映射基类
Base = declarative_base()

class TaskRecord(Base):
    """
    任务记录表。
    用于在关系型数据库中持久化存储每个代码重构任务的元数据、执行状态和最终结果。
    """
    __tablename__ = "tasks"
    
    # 任务唯一标识 UUID
    task_id = Column(String, primary_key=True, index=True)
    # 任务整体状态（例如：running, paused, completed, failed）
    status = Column(String, default="running")
    # 当前所处的重构阶段，对应 TaskPhase 枚举
    current_phase = Column(String, default="init")
    # 目标工程在宿主机的绝对路径
    project_path = Column(String)
    # 用户输入的原始自然语言重构需求
    user_request = Column(String)
    # LangGraph 工作流的全量状态（JSON序列化存储，便于快速恢复和前端展示）
    state_json = Column(JSON)
    # 任务创建时间戳
    created_at = Column(Float)
    # 任务最后更新时间戳
    updated_at = Column(Float)

class CheckpointRecord(Base):
    """
    沙箱检查点记录表。
    用于记录每次对代码修改后产生的 Git Commit 及其对应的任务阶段，为软回滚提供依据。
    """
    __tablename__ = "checkpoints"
    
    # 检查点唯一标识（通常取 Git Commit Hash 的前 12 位）
    checkpoint_id = Column(String, primary_key=True, index=True)
    # 关联的所属任务 ID
    task_id = Column(String, index=True)
    # 产生此检查点时所处的重构阶段
    phase = Column(String)
    # 完整的 Git Commit Hash，用于执行 git reset 回滚
    git_commit_hash = Column(String)
    # 检查点创建时间戳
    timestamp = Column(Float)
    # 检查点的描述信息
    description = Column(String)

# ==========================================
# 数据库引擎与会话配置
# ==========================================

# 创建数据库引擎。如果使用 SQLite，禁用多线程检查以允许 FastAPI 和后台任务共享同一连接
engine = create_engine(
    config.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {}
)

# 创建线程局部的 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    初始化数据库。
    如果配置的数据库中表不存在，则根据定义好的 ORM 模型自动建表。
    """
    Base.metadata.create_all(bind=engine)