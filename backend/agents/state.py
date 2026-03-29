from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

class TaskPhase(str, Enum):
    """
    任务阶段枚举
    标记当前多智能体工作流执行到了哪一个生命周期节点
    """
    INIT = "init"
    PLANNING = "planning"
    ANALYZING = "analyzing"
    REFACTORING = "refactoring"
    REWRITING = "rewriting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

class CheckpointMeta(BaseModel):
    """
    检查点元数据
    用于记录每次修改代码后的沙箱 Git Commit 哈希，支持事后的回滚操作
    """
    checkpoint_id: str          # 唯一标识
    phase: TaskPhase            # 触发此检查点的系统阶段
    git_commit_hash: str        # 对应的沙箱 Git commit SHA
    timestamp: float            # 创建时间戳
    description: str            # 人类可读的描述（如："执行了 extract_function 操作"）

class RefactorState(BaseModel):
    """
    全局共享状态字典 (LangGraph State)
    这是贯穿整个多智能体流程的唯一数据载体。
    每个子智能体从中读取前序节点的输出，并将自己的执行结果写回其中。
    它保证了智能体之间完全解耦。
    """
    
    # ── 用户输入 ──
    user_request: str                          # 用户最初输入的自然语言重构需求
    project_path: str                          # 待重构代码的本地或仓库原始路径
    
    # ── 当前阶段 ──
    current_phase: TaskPhase = TaskPhase.INIT  # 记录流转状态指针
    
    # ── Planner (规划智能体) 输出 ──
    project_structure: dict = {}               # 项目目录结构与初步技术栈特征概览
    subtasks: list[dict] = []                  # 大模型拆解后的可执行子任务序列
    
    # ── Analyzer (分析智能体) 输出 ──
    analysis_report: dict = {}                 # 细化的代码分析报告（基于 AST 生成的函数列表、深度等）
    code_smells: list[dict] = []               # AST 分析检测到的代码坏味列表
    dependency_graph: dict = {}                # 基于 import 分析得出的模块间依赖关系图
    
    # ── Refactorer (重构智能体) 输出 ──
    refactor_ir: list[dict] = []               # 由大模型根据报告生成的严格符合 JSON Schema 的重构指令集
    ir_validation_result: dict = {}            # Pydantic 对 IR 格式的校验结果反馈
    
    # ── Code Rewrite Engine (Node.js 执行引擎) 输出 ──
    rewrite_result: dict = {}                  # 调用 ts-morph 进行实际 AST 修改后的执行结果
    modified_files: list[str] = []             # 成功被修改并保存的文件列表
    
    # ── Validator (验证智能体) 输出 ──
    validation_result: dict = {}               # tsc/eslint 等工具的多层验证报告
    
    # ── 控制流与兜底设置 ──
    iteration_count: int = 0                   # 发生验证失败时的当前回溯迭代次数
    max_iterations: int = 3                    # 最大允许回溯次数（防止 AI 陷入无限修复的死循环）
    checkpoints: list[CheckpointMeta] = []     # 该任务下记录的所有快照检查点的有序列表
    
    # ── 交互式与反馈机制 (Human-in-the-loop) ──
    pending_user_input: dict | None = None     # 发送给前端的交互结构（当 LangGraph interrupt 挂起时使用）
    user_feedback: str | None = None           # 接收到的用户对上一个操作的自然语言反馈/批评
    
    # ── 隔离与沙箱 ──
    sandbox_id: str | None = None              # 自动生成的任务沙箱实例 ID (Task ID)
    worktree_path: str | None = None           # 实际被克隆和操作的 Git worktree 安全工作目录
    
    # ── 最终状态 ──
    final_status: Literal["pending", "success", "failed", "paused"] = "pending" # 任务最终生命周期归宿
    error_message: str | None = None           # 发生系统级错误时的详细栈化记录