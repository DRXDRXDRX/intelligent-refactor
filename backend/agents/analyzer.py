from langgraph.types import interrupt
from .state import RefactorState, TaskPhase
from rpc.client import rewrite_engine_rpc

class AnalyzerSubAgent:
    """
    分析智能体 (Analyzer Agent) - 角色相当于“系统体检/代码扫描器”
    主要职责：
    1. 根据 Planner 制定的 analyze 任务，通过 RPC 向 Node.js 端的重写引擎发出 AST 分析请求。
    2. 获取目标代码的函数/类等内部结构、外部模块依赖图以及代码坏味 (如长函数、深嵌套)。
    3. 将收集的报告发给用户确认(Interrupt)，并将结果传递给下一步的 Refactorer。
    """
    
    def __call__(self, state: RefactorState) -> dict:
        analysis = {}
        
        # 遍历所有被规划的子任务，仅处理类型为 analyze 的任务
        for task in state.subtasks:
            if task.get("type") != "analyze":
                continue
            
            # 第一步：请求 Node.js 抽取文件的基础 AST 统计信息
            ast_result = rewrite_engine_rpc.analyze_ast(
                files=task.get("target_files", []), 
                project_path=state.worktree_path
            )
            
            # 第二步：请求 Node.js 基于 AST/import 分析文件的外部依赖关系图
            dep_graph = rewrite_engine_rpc.build_dependency_graph(
                files=task.get("target_files", []), 
                project_path=state.worktree_path
            )
            
            # 第三步：请求 Node.js 基于给定的规则检测特定的代码气味
            smells = rewrite_engine_rpc.detect_code_smells(
                ast_data=ast_result,
                files=task.get("target_files", []),
                project_path=state.worktree_path
            )
            
            analysis[task["task_id"]] = {
                "ast": ast_result,
                "dependencies": dep_graph,
                "smells": smells
            }
        
        # 第四步：触发 LangGraph 的 Interrupt 中断
        # 将体检报告发送给前端/用户进行审阅
        user_decision = interrupt({
            "type": "confirm_analysis",
            "phase": "analyzing",
            "report": analysis,
            "message": "代码分析完成，以下是分析报告：",
            "options": ["confirm", "add_scope", "skip_to_refactor"]
        })
        
        # 第五步：处理人类反馈，比如是否需要扩充文件扫描范围
        if user_decision["action"] == "add_scope":
            additional_files = user_decision.get("additional_files", [])
            # 扩展范围逻辑 (待完善具体合并逻辑)
            pass
        
        # 将分析结果汇总后存入状态机，移交给 Refactorer 使用
        return {
            "analysis_report": analysis,
            "code_smells": [], # 预留聚合抽取的字段
            "dependency_graph": {}, # 预留图合并处理字段
            "current_phase": TaskPhase.ANALYZING,
        }