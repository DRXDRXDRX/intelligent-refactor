from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 创建应用路由分组，前端通过 /api/v1/refactor/* 请求重构业务
router = APIRouter(prefix="/api/v1/refactor", tags=["refactor"])

# 实例化多智能体工作流引擎
from agents.workflow import build_refactor_workflow
refactor_workflow = build_refactor_workflow()

class CreateTaskRequest(BaseModel):
    """创建任务请求载荷定义"""
    project_path: str   # 用户希望重构的本地代码路径
    user_request: str   # 自然语言描述的重构需求

class TaskResponse(BaseModel):
    """任务创建响应结构"""
    task_id: str
    status: str
    current_phase: str
    
class RespondRequest(BaseModel):
    """处理打断与确认的响应请求载荷"""
    action: str         # 用户操作，如 "confirm", "modify", "skip_to_refactor"
    data: Optional[Dict[str, Any]] = None  # 附加的数据，如用户调整的规划详情

def run_workflow(task_id: str, state: dict = None, resume: bool = False, resume_data: dict = None):
    """
    在后台线程运行 LangGraph 工作流
    """
    thread = {"configurable": {"thread_id": task_id}}
    try:
        if not resume:
            logger.info(f"Starting workflow for task {task_id}")
            # 初次启动时，向引擎注入初始状态 (initial state)
            for event in refactor_workflow.stream(state, thread):
                logger.info(f"Workflow event: {event}")
        else:
            logger.info(f"Resuming workflow for task {task_id} with data {resume_data}")
            # 目前的 LangGraph 的唤醒恢复已经通过后面的 Command 方式代替，
            # 这里的 fallback 仅作为历史参考。
            for event in refactor_workflow.stream(resume_data, thread, as_node="__interrupt__"):
                pass 
    except Exception as e:
        logger.error(f"Workflow error: {e}", exc_info=True)

@router.post("/create", response_model=TaskResponse)
def create_task(req: CreateTaskRequest, background_tasks: BackgroundTasks):
    """
    创建一个新的代码重构任务，分配 UUID 并启动后台 LangGraph 工作流执行
    """
    task_id = str(uuid.uuid4())
    
    # 构造 LangGraph 所需的全局 RefactorState 初始字典
    initial_state = {
        "user_request": req.user_request,
        "project_path": req.project_path,
        "current_phase": "init",
        "sandbox_id": task_id
    }
    
    # 借助 FastAPI 的背景任务异步跑 LangGraph 流转，不阻塞接口返回
    background_tasks.add_task(run_workflow, task_id, initial_state)
    
    return TaskResponse(
        task_id=task_id, 
        status="running", 
        current_phase="init"
    )

@router.get("/{task_id}/status")
def get_task_status(task_id: str):
    """
    获取任务当前所处的阶段、挂起状态以及内存中的完整状态机数据。
    前端需要定时轮询该接口。如果返回的 `next` 有值，代表图引擎正在等待用户通过 /respond 接口确认。
    """
    thread = {"configurable": {"thread_id": task_id}}
    state_info = refactor_workflow.get_state(thread)
    if not state_info:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return {
        "task_id": task_id,
        "state": state_info.values,
        "next": state_info.next
    }

@router.post("/{task_id}/respond")
def respond_to_task(task_id: str, req: RespondRequest, background_tasks: BackgroundTasks):
    """
    接受人类用户的决策输入，从挂起(interrupt)的位置唤醒并恢复多智能体工作流继续流转。
    """
    thread = {"configurable": {"thread_id": task_id}}
    state_info = refactor_workflow.get_state(thread)
    if not state_info:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 防止用户在工作流并未处于挂起状态时错误地发送指令
    if not state_info.next:
        return {"status": "error", "message": "Workflow is not waiting for input"}
        
    # 引入 LangGraph 特有的恢复指令 Command 封装
    from langgraph.types import Command
    
    def resume_workflow():
        try:
            # 整合用户的 action (例如 "confirm") 与附加的业务数据
            resume_data = {"action": req.action}
            if req.data:
                resume_data.update(req.data)
            logger.info(f"Resuming task {task_id} with {resume_data}")
            # 发送 Command(resume=) 可以精确唤醒上一次遇到 interrupt() 的节点
            for event in refactor_workflow.stream(Command(resume=resume_data), thread):
                logger.info(f"Resumed event: {event}")
        except Exception as e:
            logger.error(f"Error resuming: {e}", exc_info=True)

    # 同样在后台异步唤醒
    background_tasks.add_task(resume_workflow)
    
    return {"status": "resumed"}

@router.get("/{task_id}/checkpoints")
def list_checkpoints(task_id: str):
    """
    拉取状态机内存中记录的所有历史 Git Checkpoint。
    用于前端展示时光机视图和回滚列表。
    """
    thread = {"configurable": {"thread_id": task_id}}
    state_info = refactor_workflow.get_state(thread)
    if not state_info:
        return {"checkpoints": []}
    return {"checkpoints": state_info.values.get("checkpoints", [])}
