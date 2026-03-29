from langgraph.types import interrupt
from .state import RefactorState, TaskPhase
from rpc.client import rewrite_engine_rpc
from .llm_client import llm_client
from .schemas import TaskPlan
import json
import logging

logger = logging.getLogger(__name__)


class PlannerSubAgent:
    """
    规划智能体 (Planner Agent) - 角色相当于“架构师/项目经理”
    主要职责：
    1. 根据给定的沙箱项目路径，通过 RPC 获取项目的工程树结构。
    2. 将项目结构与用户原始的自然语言重构需求合并，向 LLM 提问。
    3. 解析 LLM 吐出的子任务计划，并将任务挂起(Interrupt)，等待人类审核确认。
    """

    SYSTEM_PROMPT = """你是一个代码重构项目经理。你的职责是：
    1. 分析用户的重构需求和项目结构
    2. 将需求分解为具体的、有序的子任务
    3. 每个子任务必须包含：task_id, type(analyze/refactor/validate), 
       target_files, description, dependencies
    4. 如果需求不够明确，请指出需要澄清的部分
    5. 优先安排风险较低的重构操作，高风险操作放在后面"""

    def __call__(self, state: RefactorState) -> dict:
        # 第一步：调用 Node.js 重写引擎进行工程分析（获取文件列表等）
        project_tree = rewrite_engine_rpc.scan_project(
            path=state.worktree_path)

        # 第二步：组装 Prompt 并且向 DeepSeek 等底层大模型发起请求
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user",
                "content": f"用户需求: {state.user_request}\n\n项目结构:\n{json.dumps(project_tree)}\n\n用户反馈: {state.user_feedback or '无'}"}
        ]

        logger.info(f"[Planner] 发送 LLM 请求以生成计划...")

        # 利用 Instructor 将普通文本补全转换为严格遵循 TaskPlan Pydantic Schema 的 JSON 对象
        plan = llm_client.generate_structured(messages, TaskPlan)
        plan_tasks = [task.model_dump() for task in plan.tasks]

        # 第三步：触发 LangGraph 的 Interrupt 中断
        # 此时任务将被挂起并且状态持久化，直到前端调用 /respond 接口返回用户决策
        user_decision = interrupt({
            "type": "confirm_plan",
            "phase": "planning",
            "plan": {"tasks": plan_tasks},
            "message": "以下是为您制定的重构计划，请审查：",
            "options": ["confirm", "modify", "replan"]
        })

        # 第四步：根据人类决策结果进行路由
        if user_decision["action"] == "modify":
            # 允许人类调整重构文件范围等 (暂未全面实现)
            pass  
        elif user_decision["action"] == "replan":
            # 返回用户重新提的自然语言建议，LangGraph 的边将跳回自身重新请求模型
            return {"user_feedback": user_decision.get("feedback", "")}

        # 正常流转则将生成的规划存入状态机中，交给 Analyzer
        return {
            "project_structure": project_tree,
            "subtasks": plan_tasks,
            "current_phase": TaskPhase.PLANNING,
        }
