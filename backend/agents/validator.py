from langgraph.types import interrupt
from .state import RefactorState, TaskPhase
from rpc.client import rewrite_engine_rpc

class ValidatorSubAgent:
    """
    验证智能体 (Validator Agent) - 角色相当于“质量保证(QA)/审查员”
    主要职责：
    1. 在修改后的沙箱目录中执行严格的多层级质量校验
    2. 包含：TSC类型检查、ESLint静态检查、增量单元测试(Vitest/Jest)以及通过 AST 的语义等价性检查
    3. 根据校验结果提供建议，并挂起等待人类最终确认
    """
    
    def __call__(self, state: RefactorState) -> dict:
        # 第一步：调用 Node.js 验证环境进行多层次校验
        results = {
            "static_check": rewrite_engine_rpc.run_type_check(project_path=state.worktree_path),
            "lint_check": rewrite_engine_rpc.run_lint(project_path=state.worktree_path),
            "test_check": rewrite_engine_rpc.run_tests(project_path=state.worktree_path, changed_files=state.modified_files, mode="incremental", timeout=60),
            "semantic_check": rewrite_engine_rpc.run_semantic_diff(original_path=state.project_path, refactored_path=state.worktree_path, changed_files=state.modified_files, timeout=120),
            "passed": False,
        }
        
        # 第二步：判定是否全盘通过
        results["passed"] = all([
            results["static_check"].get("success"),
            results["lint_check"].get("success"),
            results["test_check"].get("success"),
            results["semantic_check"].get("equivalent")
        ])
        
        # 第三步：触发 LangGraph 的 Interrupt 中断
        # 将验证报告和潜在报错警告反馈给人类进行裁定
        user_decision = interrupt({
            "type": "confirm_validation",
            "phase": "validating",
            "report": results,
            "message": "验证通过，可合并至主分支" if results["passed"] else "验证阶段发现警告或错误，请人工定夺",
            "options": ["accept", "ignore_warnings", "redo"]
        })
        
        # 如果人类强行要求忽略警告，我们强制将状态改写为 True，便于后续路由导向 Finalize
        if user_decision["action"] == "ignore_warnings":
            results["passed"] = True
            
        return {
            "validation_result": results,
            "current_phase": TaskPhase.VALIDATING,
        }