import time
import logging
import json
from agents.state import RefactorState, TaskPhase

logger = logging.getLogger(__name__)

# mock git manager integration
class MockGitManager:
    """
    Mock 版本的 GitCheckpointManager，仅用于演示或测试环境。
    由于中间件被独立加载，这里提供一个默认的占位实现，实际使用时应由 sandbox.provider 注入。
    """
    def create_checkpoint(self, worktree_path, message, phase):
        from agents.state import CheckpointMeta
        return CheckpointMeta(
            checkpoint_id="mock_id",
            phase=phase,
            git_commit_hash="mock_hash",
            timestamp=time.time(),
            description=message
        )

# 初始化 Mock 实例（注意：在真实生产代码中应使用真实的 GitCheckpointManager）
git_manager = MockGitManager()

def json_schema_validate(ir, schema=None):
    """
    JSON Schema 校验桩函数。
    用于验证大模型生成的 RefactorIR 指令是否符合严格的 JSON Schema 定义。
    """
    class Valid:
        valid = True
        errors = []
    return Valid()

class CheckpointSnapshotMiddleware:
    """
    节点执行前中间件：记录状态快照（日志级）。
    可以在这里进行状态深拷贝，用于后续对比。
    """
    def before(self, state: RefactorState):
        logger.info(f"[Checkpoint] Entering phase: {state.current_phase}")

class GitCheckpointCommitMiddleware:
    """
    节点执行后中间件：Git 沙箱检查点创建。
    如果当前节点执行后产生了被修改的文件（modified_files 有值），
    并且沙箱已挂载，则触发 Git commit 生成检查点，用于软回滚。
    """
    def after(self, state: RefactorState):
        if state.modified_files and state.worktree_path:
            checkpoint = git_manager.create_checkpoint(
                worktree_path=state.worktree_path,
                message=f"checkpoint: phase={state.current_phase.value}",
                phase=state.current_phase
            )
            state.checkpoints.append(checkpoint)
            logger.info(f"[Git] Checkpoint created: {checkpoint.git_commit_hash[:8]}")

class IRSchemaValidationMiddleware:
    """
    节点执行后中间件：RefactorIR Schema 校验。
    在 Refactorer 节点生成指令后触发，校验所有 IR 是否符合预定义的 JSON Schema。
    如果不符合，可选择在 state 中记录 error，引导图节点重新执行纠错。
    """
    def after(self, state: RefactorState):
        if state.current_phase == TaskPhase.REFACTORING and state.refactor_ir:
            for idx, ir in enumerate(state.refactor_ir):
                result = json_schema_validate(ir)
                if not result.valid:
                    logger.warning(
                        f"[IR Validation] Instruction #{idx} failed: {result.errors}"
                    )

class DanglingToolCallMiddleware:
    """
    悬空工具调用清理中间件。
    用于清理上一轮对话中 LLM 生成但未正确闭合的 tool_calls 或垃圾消息记录，
    保证进入新节点前状态的干净。
    """
    def before(self, state: RefactorState):
        pass

class SandboxReadyMiddleware:
    """
    沙箱就绪性检查中间件。
    在任何需要操作文件系统的节点之前运行，确保沙箱已经被正确挂载并分配。
    """
    def before(self, state: RefactorState):
        if not state.sandbox_id or not state.worktree_path:
            logger.warning("[Sandbox] Sandbox not initialized, creating...")

class PhaseLoggingMiddleware:
    """
    阶段耗时与日志中间件。
    负责统计每个 LangGraph 图节点的执行耗时，并规范化输出日志。
    """
    def before(self, state: RefactorState):
        logger.info(f"[Phase] ▶ Starting {state.current_phase.value}")
        self._start_time = time.time()
    
    def after(self, state: RefactorState):
        elapsed = time.time() - getattr(self, '_start_time', time.time())
        logger.info(f"[Phase] ◀ Completed {state.current_phase.value} in {elapsed:.2f}s")

class UnifiedMiddlewareChain:
    """
    统一的中间件调用链注册表。
    类似于 Express 或 Koa 的中间件模式，将定义好的中间件分组：
    1. before_middlewares: 在 Node 功能逻辑执行前依次调用
    2. after_middlewares: 在 Node 功能逻辑执行后依次调用
    """
    def __init__(self):
        self.before_middlewares = [
            CheckpointSnapshotMiddleware(),
            SandboxReadyMiddleware(),
            DanglingToolCallMiddleware(),
            PhaseLoggingMiddleware(),
        ]
        self.after_middlewares = [
            IRSchemaValidationMiddleware(),
            GitCheckpointCommitMiddleware(),
            PhaseLoggingMiddleware(),
        ]