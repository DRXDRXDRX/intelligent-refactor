from langgraph.types import interrupt
from .state import RefactorState, TaskPhase
from .schemas import RefactorIRSchema
from .llm_client import llm_client
import json
import logging
import os

logger = logging.getLogger(__name__)

class RefactorerSubAgent:
    """重构智能体：基于分析报告，输出 RefactorIR 指令集"""

    SYSTEM_PROMPT = """你是一个专业的 AST 代码重构专家。
你的职责是将人类的重构意图以及项目的分析报告，转换为极其精确的、符合 JSON Schema 规范的 RefactorIR 指令集。

对于 extract_function 动作，你必须指定:
- target: 包含 file (如 main.js), symbol_name (原函数名), symbol_type (通常是 function)
- parameters: 包含 new_function_name (新提取出的函数名), parameters_to_extract (需要传递给新函数的变量名列表), 
              以及 extraction_points (要提取的语句行号范围，需要准确)。

请注意，返回的结果必须符合 RefactorIRSchema。"""

    def __call__(self, state: RefactorState) -> dict:
        logger.info("[Refactorer] 发送 LLM 请求生成 RefactorIR...")
        
        # 组装 Prompt，将之前的上下文全部带入
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"用户原始需求: {state.user_request}\n\n"
                                        f"Planner 子任务规划: {json.dumps(state.subtasks, ensure_ascii=False)}\n\n"
                                        f"Analyzer 静态分析报告 (包含AST节点、坏味等): {json.dumps(state.analysis_report, ensure_ascii=False)}\n\n"
                                        f"要求：请根据上面的任务和分析，生成确切的 RefactorIR 修改指令。"}
        ]
        
        # 调用大模型生成结构化数据
        ir_plan = llm_client.generate_structured(messages, RefactorIRSchema)
        # 将 Pydantic 对象序列化为字典列表以便传递给外部系统和 Node.js
        ir_instructions = [ir.model_dump() for ir in ir_plan.instructions]

        validation_dict = {"valid": True, "errors": []}
        
        user_decision = interrupt({
            "type": "confirm_ir",
            "phase": "refactoring",
            "refactor_ir": ir_instructions,
            "message": "以下是重构方案（RefactorIR 指令集），您可以逐条审查或编辑：",
            "options": ["confirm_all", "edit_instructions", "regenerate"]
        })
        
        if user_decision["action"] == "edit_instructions":
            pass # TODO: apply edits
        elif user_decision["action"] == "regenerate":
            return {"user_feedback": user_decision.get("feedback", "")}
        
        return {
            "refactor_ir": ir_instructions,
            "ir_validation_result": validation_dict,
            "current_phase": TaskPhase.REFACTORING,
        }
