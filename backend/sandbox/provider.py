from abc import ABC, abstractmethod
from .git_manager import GitCheckpointManager

class Sandbox(ABC):
    """
    沙箱环境抽象基类。
    用于定义代码重构过程中的隔离执行环境，以保证重构过程不污染原始代码库。
    """
    pass

class LocalSandbox(Sandbox):
    """
    本地沙箱实现。
    使用本地机器的 Git worktree 来提供文件系统级别的隔离。
    """
    def __init__(self, sandbox_id: str, worktree_path: str, git_manager: GitCheckpointManager):
        """
        :param sandbox_id: 沙箱唯一标识，通常与任务 task_id 相同
        :param worktree_path: 分配给该沙箱的本地绝对路径（即 git worktree 的目录）
        :param git_manager: 管理该沙箱 Git 操作的管理器实例
        """
        self.sandbox_id = sandbox_id
        self.worktree_path = worktree_path
        self.git_manager = git_manager

class DockerSandbox(Sandbox):
    """
    Docker 容器沙箱实现。
    利用 Docker 容器隔离运行重构任务和进程。
    """
    def __init__(self, sandbox_id: str, container):
        """
        :param sandbox_id: 沙箱唯一标识，通常与任务 task_id 相同
        :param container: aiodocker 返回的容器实例
        """
        self.sandbox_id = sandbox_id
        self.container = container

class SandboxProvider(ABC):
    """
    沙箱提供者抽象基类。
    定义了创建(acquire)、获取(get)和释放(release)沙箱生命周期的标准接口。
    """
    @abstractmethod
    async def acquire(self, task_id: str, project_path: str) -> Sandbox:
        """为特定任务获取或分配一个隔离的沙箱环境"""
        pass
    
    @abstractmethod
    async def get(self, sandbox_id: str) -> Sandbox:
        """根据 ID 获取已经分配的沙箱实例"""
        pass
    
    @abstractmethod
    async def release(self, sandbox_id: str):
        """释放分配的沙箱资源，清理遗留文件或容器"""
        pass

class LocalSandboxProvider(SandboxProvider):
    """
    本地沙箱环境的生命周期管理器。
    使用 GitCheckpointManager 基于 worktree 技术来分配隔离的文件目录。
    """
    def __init__(self):
        # 缓存当前活跃的沙箱实例
        self._active: dict[str, LocalSandbox] = {}
    
    async def acquire(self, task_id: str, project_path: str) -> LocalSandbox:
        """
        获取一个本地沙箱环境。
        如果在活跃字典中已存在则直接返回；否则基于源项目创建一个新的 Git worktree。
        """
        if task_id in self._active:
            return self._active[task_id]
        
        # 初始化基于 worktree 的本地沙箱
        git_manager = GitCheckpointManager(project_path)
        worktree_path = git_manager.create_worktree(task_id)
        
        sandbox = LocalSandbox(
            sandbox_id=task_id,
            worktree_path=worktree_path,
            git_manager=git_manager,
        )
        self._active[task_id] = sandbox
        return sandbox
    
    async def get(self, sandbox_id: str) -> Sandbox:
        """获取沙箱实例"""
        return self._active.get(sandbox_id)

    async def release(self, sandbox_id: str):
        """释放本地沙箱，从活跃字典中移除并调用 git_manager 清理 worktree 目录及分支"""
        if sandbox_id in self._active:
            sandbox = self._active.pop(sandbox_id)
            sandbox.git_manager.cleanup_worktree(sandbox_id)

class AioSandboxProvider(SandboxProvider):
    """
    异步 Docker 沙箱环境的生命周期管理器。
    使用 aiodocker 来调度和销毁用于执行隔离任务的 Docker 容器。
    """
    def __init__(self, docker_url: str = "unix:///var/run/docker.sock"):
        """
        :param docker_url: Docker 守护进程的连接地址，默认连接到本地 sock
        """
        import aiodocker
        self.docker = aiodocker.Docker(url=docker_url)
        # 缓存当前活跃的 Docker 沙箱实例
        self._active: dict[str, DockerSandbox] = {}
    
    async def acquire(self, task_id: str, project_path: str) -> DockerSandbox:
        """
        启动一个新的 Docker 容器作为隔离的沙箱环境。
        如果已存在则直接返回。
        这里设置了 CPU 和内存等资源限制，并将项目挂载到容器内部。
        """
        if task_id in self._active:
            return self._active[task_id]
        
        container = await self.docker.containers.run(
            config={
                # 需要预先构建好重写引擎的基础镜像
                "Image": "refactor-engine:latest",
                "HostConfig": {
                    # 将需要重构的项目根目录挂载到容器内的 /mnt/project 下，可读写
                    "Binds": [f"{project_path}:/mnt/project:rw"],
                    # 资源隔离配置：限制最大内存为 2GB
                    "Memory": 2 * 1024 * 1024 * 1024,
                    # CPU 限制配额（例如限制 CPU 使用率）
                    "CpuQuota": 200000,
                    "CpuPeriod": 100000,
                },
            },
            name=f"refactor-sandbox-{task_id}",
        )
        
        sandbox = DockerSandbox(sandbox_id=task_id, container=container)
        self._active[task_id] = sandbox
        return sandbox
        
    async def get(self, sandbox_id: str) -> Sandbox:
        """获取 Docker 沙箱实例"""
        return self._active.get(sandbox_id)

    async def release(self, sandbox_id: str):
        """释放 Docker 沙箱，强行删除运行中的隔离容器"""
        if sandbox_id in self._active:
            sandbox = self._active.pop(sandbox_id)
            await sandbox.container.delete(force=True)
