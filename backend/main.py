from fastapi import FastAPI
import uvicorn
from api.routes import router as refactor_router
from api.websocket import websocket_endpoint
import os

# 允许 LangGraph 在进行 SQLite 状态检查点持久化时，反序列化自定义枚举类型
os.environ["LANGGRAPH_ALLOW_MSGPACK_MODULES"] = "agents.state"

# 初始化 FastAPI 应用程序实例
app = FastAPI(
    title="Intelligent Refactor API", 
    version="0.1.0",
    description="智能代码重构系统后端网关 API"
)

@app.get("/health")
def health_check():
    """
    健康检查接口
    用于容器编排(Docker/K8s)或负载均衡器确认当前服务是否存活
    """
    return {"status": "ok"}

# 注册重构核心业务的 HTTP 路由
app.include_router(refactor_router)

# 注册 WebSocket 路由，用于前端实时接收重构状态推送与交互通知
app.add_api_websocket_route(
    "/api/v1/refactor/{task_id}/ws", websocket_endpoint)

if __name__ == "__main__":
    # 启动 ASGI 服务器
    # 在开发模式下使用 reload=True 开启热更新
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
