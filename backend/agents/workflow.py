from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import functools
from .state import RefactorState, TaskPhase
from .planner import PlannerSubAgent
from .analyzer import AnalyzerSubAgent
from .refactorer import RefactorerSubAgent
from .code_rewrite_node import CodeRewriteNode
from .validator import ValidatorSubAgent
from sandbox.provider import LocalSandboxProvider
from middleware.chain import UnifiedMiddlewareChain
import asyncio

# 初始化沙箱提供器和中间件执行链
sandbox_provider = LocalSandboxProvider()
middleware_chain = UnifiedMiddlewareChain()


def wrap_with_middleware(node_func):
    """
    节点包装器装饰器：用于在 LangGraph 的每个图节点执行前后注入中间件逻辑。
    包含日志记录、参数校验、异常捕获等。
    """
    @functools.wraps(node_func)
    def wrapper(state: RefactorState, *args, **kwargs):
        # 执行前置中间件
        for mw in middleware_chain.before_middlewares:
            mw.before(state)

        # 核心节点逻辑执行
        result = node_func(state, *args, **kwargs)

        # 将节点返回的字典结果同步更新到全局状态对象上，以供后置中间件使用
        if isinstance(result, dict):
            for k, v in result.items():
                if hasattr(state, k):
                    setattr(state, k, v)

        # 执行后置中间件
        for mw in middleware_chain.after_middlewares:
            mw.after(state)

        return result
    return wrapper


def init_sandbox_node(state: RefactorState) -> dict:
    """
    初始化沙箱节点：
    为当前的重构任务在独立的工作区克隆代码目录 (基于 Git worktree)。
    """
    if state.sandbox_id and state.worktree_path:
        return {"current_phase": TaskPhase.INIT}

    # 异步申请分配沙箱资源
    sandbox = asyncio.run(sandbox_provider.acquire(
        task_id=state.sandbox_id or "default_task",
        project_path=state.project_path
    ))

    return {
        "current_phase": TaskPhase.INIT,
        "worktree_path": sandbox.worktree_path
    }


def finalize_node(state: RefactorState) -> dict:
    """
    结束节点：
    标记任务成功完成。可在此添加消息通知、数据归档等收尾操作。
    """
    return {"current_phase": TaskPhase.COMPLETED, "final_status": "success"}


def route_after_planner(state: RefactorState) -> str:
    """规划节点执行后的路由判定"""
    if state.user_feedback and "replan" in state.user_feedback.lower():
        return "replan"
    if state.subtasks:
        return "analyzer"
    return "replan"


def route_after_analyzer(state: RefactorState) -> str:
    """分析节点执行后的路由判定"""
    if state.user_feedback and "scope" in state.user_feedback.lower():
        return "add_scope"
    return "refactorer"


def route_after_refactorer(state: RefactorState) -> str:
    """重构(IR生成)节点执行后的路由判定"""
    if state.user_feedback and "regenerate" in state.user_feedback.lower():
        return "regenerate"
    return "code_rewriter"


def route_after_rewrite(state: RefactorState) -> str:
    """AST代码修改节点执行后的路由判定"""
    if state.user_feedback and "rollback" in state.user_feedback.lower():
        return "rollback_to_refactorer"
    return "validator"


def route_after_validation(state: RefactorState) -> str:
    """质量验证节点执行后的路由判定"""
    if state.validation_result.get("passed"):
        return "finalize"

    # 防止多次重试导致死循环
    if state.iteration_count >= state.max_iterations:
        return "end_failed"

    # 默认退回重构节点重新生成
    return "refactorer"


def build_refactor_workflow():
    """
    构建多智能体重构状态图 (LangGraph StateGraph)
    核心编排逻辑，定义了从 Planner -> Analyzer -> Refactorer -> Rewriter -> Validator 的全局流转与条件中断分支。
    """
    workflow = StateGraph(RefactorState)

    # 注册系统各个执行节点，并统一经过中间件包装
    workflow.add_node("init_sandbox", wrap_with_middleware(init_sandbox_node))
    workflow.add_node("planner", wrap_with_middleware(PlannerSubAgent()))
    workflow.add_node("analyzer", wrap_with_middleware(AnalyzerSubAgent()))
    workflow.add_node("refactorer", wrap_with_middleware(RefactorerSubAgent()))
    workflow.add_node("code_rewriter", wrap_with_middleware(CodeRewriteNode()))
    workflow.add_node("validator", wrap_with_middleware(ValidatorSubAgent()))
    workflow.add_node("finalize", wrap_with_middleware(finalize_node))

    # 定义工作流的唯一入口
    workflow.set_entry_point("init_sandbox")
    workflow.add_edge("init_sandbox", "planner")

    # 定义各个节点之间的带状态条件判定边
    workflow.add_conditional_edges("planner", route_after_planner, {
        "analyzer": "analyzer",
        "replan": "planner",
    })

    workflow.add_conditional_edges("analyzer", route_after_analyzer, {
        "refactorer": "refactorer",
        "add_scope": "analyzer",
    })

    workflow.add_conditional_edges("refactorer", route_after_refactorer, {
        "code_rewriter": "code_rewriter",
        "regenerate": "refactorer",
    })

    workflow.add_conditional_edges("code_rewriter", route_after_rewrite, {
        "validator": "validator",
        "rollback_to_refactorer": "refactorer",
    })

    workflow.add_conditional_edges("validator", route_after_validation, {
        "finalize": "finalize",
        "refactorer": "refactorer",
        "planner": "planner",
        "end_failed": END,
    })

    # 设置结束出口
    workflow.add_edge("finalize", END)

    # 初始化基于 SQLite 的持久化组件，支持任务挂起 (Interrupt) 与恢复
    conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        # 为防止 Enum 类型序列化报警，提前注入反序列化允许清单
        import os
        os.environ["LANGGRAPH_ALLOW_MSGPACK_MODULES"] = "agents.state"
        checkpointer = SqliteSaver(conn)
        # 编译并返回可执行的状态图实例
        return workflow.compile(checkpointer=checkpointer)
    except Exception as e:
        import logging
        logging.error(f"Failed to initialize checkpointer: {e}")
        # 降级：无记忆执行
        return workflow.compile()
