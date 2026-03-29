from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

# ============================================================================
# Planner (规划智能体) 输出的数据结构 Schema
# 用于指导大模型 (LLM) 以 JSON 格式输出任务拆解计划
# ============================================================================

class PlannerTask(BaseModel):
    """
    单个重构子任务的定义。
    大模型在进行复杂重构时，需要将大目标拆解为多个有序的小任务。
    """
    task_id: str = Field(..., description="子任务的唯一标识 ID (如: task-1)")
    type: Literal["analyze", "refactor", "validate"] = Field(..., description="该子任务的类型：分析、重构修改、或验证")
    target_files: List[str] = Field(..., description="该任务需要作用的相对文件路径列表")
    description: str = Field(..., description="对该任务具体要做什么的自然语言描述")
    dependencies: List[str] = Field(default_factory=list, description="前置依赖任务的 ID 列表，用于决定执行顺序")

class TaskPlan(BaseModel):
    """
    总体任务计划。
    PlannerSubAgent 的结构化输出模型。
    """
    tasks: List[PlannerTask] = Field(..., description="分解后的重构子任务序列")

# ============================================================================
# Refactorer (重构智能体) 输出的数据结构 Schema
# 即 RefactorIR (Intermediate Representation, 中间表示)
# 这是系统中最核心的设计：将自然语言转化为确定性的、可被代码引擎执行的 JSON 指令
# ============================================================================

class SemanticTarget(BaseModel):
    """
    语义目标定位器。
    由于大模型通常无法给出精确的 AST Node ID 或代码行号，
    因此要求模型输出目标的"语义特征"（如文件名、类名、方法名），
    随后由后端的 Semantic Resolver 解析为准确的 AST 节点。
    """
    file: str = Field(..., description="目标所在的文件相对路径")
    symbol_name: str = Field(..., description="目标的符号名称，如函数名、类名、变量名等")
    symbol_type: Literal["function", "class", "variable", "interface", "type_alias", "component", "hook", "method", "property"] = Field(..., description="目标在语法树中的类型")
    parent_scope: Optional[str] = Field(None, description="可选，父级作用域名称（例如：类中的某个方法，其 parent_scope 就是类名），用于解决同名冲突")
    context_hint: Optional[str] = Field(None, description="可选，目标周围的代码上下文特征提示，用于模糊匹配")
    line_hint: Optional[int] = Field(None, description="可选，目标大概所在的代码行号（仅作参考，不严格依赖）")

class RefactorInstruction(BaseModel):
    """
    单一的重构指令 (Refactor IR)。
    描述了对代码进行的一个原子级的变更操作。
    """
    id: str = Field(..., description="指令的唯一标识 ID")
    action: str = Field(..., description="重构动作类型，例如：extract_function, rename_symbol, inline_variable, move_module 等")
    target: SemanticTarget = Field(..., description="要操作的代码目标定位信息")
    parameters: Dict[str, Any] = Field(..., description="执行该动作所需的参数字典。例如重命名时提供 new_name，提取函数时提供 new_function_name")
    dependencies: List[str] = Field(default_factory=list, description="依赖的其他指令 ID 列表，保证执行的先后拓扑顺序")
    impact_scope: List[str] = Field(default_factory=list, description="评估该操作可能会影响到的其他文件或模块范围")
    risk_level: Literal["low", "medium", "high"] = Field(..., description="该项重构操作的风险评估等级")
    description: str = Field(..., description="对该重构动作的简短人类可读说明")

class RefactorIRSchema(BaseModel):
    """
    完整的重构指令集 (Refactor Intermediate Representation)。
    RefactorerSubAgent 的结构化输出模型，将交由底层 Node.js 引擎逐条执行。
    """
    version: str = Field("2.0", description="IR 协议的版本号")
    instructions: List[RefactorInstruction] = Field(..., description="原子的重构指令列表")
    execution_order: List[str] = Field(..., description="根据依赖关系拓扑排序后的指令 ID 执行序列")
    global_impact: Dict[str, Any] = Field(..., description="对整个工程造成的全局影响评估摘要")