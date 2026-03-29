from langgraph.types import interrupt
from .state import RefactorState, TaskPhase
from rpc.client import rewrite_engine_rpc
from sandbox.git_manager import GitCheckpointManager

class CodeRewriteNode:
    """
    代码重写节点 (Code Rewrite Engine Node) - 唯一非 LLM 节点
    主要职责：
    1. 接收 Refactorer 生成的抽象 IR，通过 Semantic Resolver 解析为准确的 AST Node ID
    2. 调用 Node.js 重写引擎进行确定性的代码 AST 修改
    3. 利用 Git 创建检查点，为软回滚提供保障
    """
    
    def __call__(self, state: RefactorState) -> dict:
        # 第一步：Semantic Resolver
        # 将 LLM 输出的文本级语义定位转换为底层 AST 解析器能看懂的精确节点标识 (ID/Pos)
        resolved_ir = rewrite_engine_rpc.resolve_targets(
            instructions=state.refactor_ir, 
            project_path=state.worktree_path
        )
        
        # 第二步：Execute RefactorIR 
        # 发送具有准确目标的 IR 给 Node.js (基于 ts-morph 实际修改沙箱文件)
        result_dict = rewrite_engine_rpc.execute_refactor_ir(
            instructions=resolved_ir["instructions"], 
            project_path=state.worktree_path
        )
        
        # 第三步：创建 Git 沙箱检查点 (Git checkpoint)
        # 将 AST 修改后的文件进行 git add & commit 并记录 Hash 值
        git_manager = GitCheckpointManager(state.project_path)
        checkpoint = git_manager.create_checkpoint(
            worktree_path=state.worktree_path,
            message=f"refactor: applied {len(state.refactor_ir)} IR instructions",
            phase=TaskPhase.REWRITING
        )
        
        # 第四步：挂起并让人类审核这次代码变更 (Diff)
        user_decision = interrupt({
            "type": "confirm_rewrite",
            "phase": "rewriting",
            "diff": "mock diff", # 待补充调用 Git 查 diff 的逻辑
            "modified_files": result_dict.get("modified_files", []),
            "message": "代码重写完成，请审查以下变更：",
            "options": ["confirm", "rollback", "selective_apply"]
        })
        
        # 第五步：处理用户的回滚/审核请求
        if user_decision["action"] == "rollback":
            if checkpoint:
                # 使用 Git 分支特性，创建 fork 分支并 Hard reset 撤销到修改之前
                fork_branch = git_manager.soft_rollback(
                    state.worktree_path, checkpoint.git_commit_hash
                )
                feedback = f"用户要求回滚重写结果（原分支已保留为 {fork_branch}）"
            else:
                feedback = "用户要求回滚重写结果（无变更可回滚）"
                
            # 退回至上游 Refactorer 节点让 LLM 重新生成操作指令
            return {
                "user_feedback": feedback,
                "current_phase": TaskPhase.REFACTORING,
            }
        
        # 保存结果并流转入 Validator 验证节点
        return {
            "rewrite_result": result_dict,
            "modified_files": result_dict.get("modified_files", []),
            "checkpoints": state.checkpoints + ([checkpoint] if checkpoint else []),
            "current_phase": TaskPhase.REWRITING,
        }