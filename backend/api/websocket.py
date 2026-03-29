from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    WebSocket 连接管理器。
    负责维护服务器与前端客户端之间的实时长连接，
    用于向前端推送代码重构进度、流式日志和人机交互(Human-in-the-loop)中断请求。
    """
    def __init__(self):
        # 使用字典缓存当前活跃的 WebSocket 连接，键为 task_id
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """
        接受并保存来自客户端的新 WebSocket 连接。
        :param task_id: 客户端订阅的任务 ID
        """
        await websocket.accept()
        self.active_connections[task_id] = websocket
        logger.info(f"[WebSocket] Client connected for task: {task_id}")

    def disconnect(self, task_id: str):
        """
        当客户端断开连接时，从活跃连接字典中移除该任务的 WebSocket 实例。
        """
        if task_id in self.active_connections:
            del self.active_connections[task_id]
            logger.info(f"[WebSocket] Client disconnected for task: {task_id}")

    async def send_message(self, task_id: str, message: dict):
        """
        向指定任务的客户端推送 JSON 格式的消息。
        
        :param task_id: 目标任务 ID
        :param message: 要推送的数据字典（如状态更新、进度条、差异代码等）
        """
        if task_id in self.active_connections:
            try:
                await self.active_connections[task_id].send_json(message)
            except Exception as e:
                logger.error(f"[WebSocket] Failed to send message to task {task_id}: {e}")

# 实例化全局单例连接管理器
manager = ConnectionManager()

# 这个函数将被导入到 main.py 注册为 FastAPI 的 WebSocket 路由
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    处理客户端的 WebSocket 请求。
    建立连接后，循环监听可能来自客户端的消息，并在客户端主动断开时进行清理。
    """
    await manager.connect(task_id, websocket)
    try:
        while True:
            # 持续监听客户端发送过来的文本消息
            # 在目前的重构系统设计中，前端主要作为接收端，此处仅做占位监听以保持连接存活
            data = await websocket.receive_text()
            logger.debug(f"[WebSocket] Received message from {task_id}: {data}")
            # 如果需要处理客户端发来的指令（例如强行中止任务），可以在此处扩展逻辑
    except WebSocketDisconnect:
        # 捕获断开异常，进行清理释放
        manager.disconnect(task_id)