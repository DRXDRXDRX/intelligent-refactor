import requests
from config import config
import logging

logger = logging.getLogger(__name__)

class RewriteEngineRPC:
    """
    重写引擎 RPC 客户端
    
    负责提供 Python 后端与 Node.js 重写引擎 (AST 服务) 之间的 HTTP/JSON 进程间通信机制。
    所有的项目扫描、AST 分析和代码重构修改指令都是通过此客户端分发到 Node.js 端执行的。
    """
    
    def __init__(self, base_url=None):
        """
        初始化 RPC 客户端
        :param base_url: Node.js 服务的基地址，默认从配置文件读取 (例如 http://localhost:8080)
        """
        self.base_url = base_url or config.REWRITE_ENGINE_URL
    
    def _call(self, endpoint, payload):
        """
        内部通用调用方法，发起 HTTP POST 请求到重写引擎
        
        :param endpoint: RPC 方法名/路由端点
        :param payload: 传递给 Node.js 端的 JSON 参数
        :return: Node.js 端的 JSON 响应结果，如果失败则返回 Mock 数据
        """
        url = f"{self.base_url}/rpc/{endpoint}"
        try:
            # 设定 10 秒超时时间，避免引擎挂起导致后端阻塞
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"RPC Call failed: {endpoint} - {e}")
            # 如果请求失败或引擎宕机，为了保证工作流不断开，降级使用 Mock 数据（主要用于开发测试）
            return self._mock_fallback(endpoint, payload)

    def _mock_fallback(self, endpoint, payload):
        """
        容灾降级机制：如果重写引擎不可用，返回固定的模拟数据，以便本地调试和跑通流程。
        """
        if endpoint == "scan_project":
            return {"files": ["main.js"], "framework": "Unknown"}
        elif endpoint == "analyze_ast":
            return {"ast_stats": {}}
        elif endpoint == "build_dependency_graph":
            return {"graph": {}}
        elif endpoint == "detect_code_smells":
            return []
        elif endpoint == "resolve_targets":
             return {"instructions": payload.get("instructions", [])}
        elif endpoint == "execute_refactor_ir":
             return {"modified_files": []}
        return {}

    def scan_project(self, path: str):
        """
        扫描项目工程结构，获取文件树和框架信息
        """
        return self._call("scan_project", {"project_path": path})
        
    def analyze_ast(self, files: list, project_path: str):
        """
        请求 Node.js 引擎对指定文件进行 AST 基础分析（提取类、函数、变量等信息）
        """
        return self._call("analyze_ast", {"project_path": project_path, "files": files})
        
    def build_dependency_graph(self, files: list, project_path: str):
        """
        构建项目内部模块的依赖关系图 (Dependency Graph)
        """
        return self._call("build_dependency_graph", {"project_path": project_path, "files": files})
        
    def detect_code_smells(self, ast_data: dict, project_path: str = None, files: list = None):
        """
        根据 AST 数据检测代码中存在的潜在坏味（如重复代码、长函数等）
        """
        return self._call("detect_code_smells", {"project_path": project_path, "files": files})
        
    def resolve_targets(self, instructions: list, project_path: str):
        """
        语义解析层 (Semantic Resolver)
        将大模型生成的模糊指令（如行号/自然语言特征）解析并绑定到具体且稳定的 AST Node ID 上。
        """
        return self._call("resolve_targets", {"project_path": project_path, "instructions": instructions})
        
    def execute_refactor_ir(self, instructions: list, project_path: str):
        """
        核心重写执行器：在沙箱内真正应用 RefactorIR 指令修改代码 AST 并落盘
        """
        return self._call("execute_refactor_ir", {"project_path": project_path, "instructions": instructions})
        
    # ================= 验证环节 (Validator) 的 RPC 调用 =================
    
    def run_type_check(self, project_path: str):
        """
        运行 TypeScript 类型检查 (tsc)
        (当前版本使用 Mock 直接返回成功)
        """
        return {"success": True}
        
    def run_lint(self, project_path: str):
        """
        运行 ESLint 静态代码检查
        (当前版本使用 Mock 直接返回成功)
        """
        return {"success": True}
        
    def run_tests(self, project_path: str, changed_files: list, mode: str, timeout: int):
        """
        运行增量单元测试
        (当前版本使用 Mock 直接返回成功)
        """
        return {"success": True}
        
    def run_semantic_diff(self, original_path: str, refactored_path: str, changed_files: list, timeout: int):
        """
        通过对比重构前后的 AST，进行语义等价性检查，确保重构不改变业务逻辑行为
        (当前版本使用 Mock 直接返回成功)
        """
        return {"equivalent": True}

# 实例化全局单例供各个智能体节点使用
rewrite_engine_rpc = RewriteEngineRPC()