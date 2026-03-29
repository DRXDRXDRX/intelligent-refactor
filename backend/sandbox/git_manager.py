import os
import time
import logging
from git import Repo
from agents.state import CheckpointMeta, TaskPhase

logger = logging.getLogger(__name__)


class GitCheckpointManager:
    """
    基于 Git worktree 的检查点与软回滚管理器
    
    主要功能：
    1. 为每个重构任务创建独立的 Git worktree 沙箱，避免污染主工作区
    2. 在重构的各个阶段（如代码修改后）创建 Git commit 作为检查点
    3. 支持在出现问题时，通过分支 fork 的形式进行软回滚（保留出错现场）
    4. 最终可将沙箱中的修改 squash 合并回主分支
    """

    def __init__(self, project_path: str):
        """
        初始化 Git 管理器
        :param project_path: 目标项目的绝对路径（必须是一个 Git 仓库）
        """
        self.repo = Repo(project_path)
        self.project_path = project_path

    def create_worktree(self, task_id: str) -> str:
        """
        为指定任务创建一个隔离的 Git worktree 沙箱环境
        
        :param task_id: 任务唯一标识 UUID
        :return: 创建的 worktree 的绝对路径
        """
        # 为该任务创建专属分支
        branch_name = f"refactor/{task_id}"
        # 定义 worktree 存放的相对目录
        worktree_path = f".refactor-workspaces/{task_id}"
        abs_worktree_path = os.path.abspath(worktree_path)

        # 检查是否已经存在且为有效的 Git 仓库
        if os.path.exists(abs_worktree_path) and os.path.isdir(os.path.join(abs_worktree_path, ".git")):
            logger.info(f"[Git] Worktree already exists: {abs_worktree_path}")
            return abs_worktree_path

        # 确保父目录存在
        os.makedirs(os.path.dirname(abs_worktree_path), exist_ok=True)

        try:
            # 尝试创建分支，如果已存在则忽略异常
            self.repo.git.branch(branch_name)
        except Exception:
            pass

        try:
            # 如果目录存在但不是有效的 repo，强制清理脏数据
            if os.path.exists(abs_worktree_path):
                import shutil
                shutil.rmtree(abs_worktree_path)

            # 在添加新的 worktree 之前，先清理失效的 worktree 记录
            self.repo.git.worktree("prune")
            # 添加新的 worktree，并绑定到对应的任务分支
            self.repo.git.worktree("add", abs_worktree_path, branch_name)
        except Exception as e:
            logger.error(f"[Git] Failed to create worktree: {e}")
            # 如果 worktree 创建失败（例如目标不是 Git 仓库或权限问题）
            # 优雅降级：返回原始项目路径以避免系统崩溃
            logger.warning(
                f"[Git] Falling back to main project path: {self.project_path}")
            return self.project_path

        logger.info(
            f"[Git] Worktree created: {abs_worktree_path} (branch: {branch_name})")
        return abs_worktree_path

    def create_checkpoint(self, worktree_path: str, message: str, phase: TaskPhase) -> CheckpointMeta:
        """
        在给定的 worktree 中创建一个 Git commit 作为检查点
        
        :param worktree_path: 沙箱环境绝对路径
        :param message: 检查点描述信息
        :param phase: 当前处于的重构阶段
        :return: 包含 commit_hash 和元数据的检查点对象，如果没有变更则返回 None
        """
        try:
            wt_repo = Repo(worktree_path)
            # 添加所有变更（包括 untracked 文件）
            wt_repo.git.add("-A")

            # 如果没有变更也没有未追踪的文件，则跳过创建检查点
            if not wt_repo.is_dirty() and not wt_repo.untracked_files:
                return None

            # 提交检查点，信息中包含阶段标识
            commit = wt_repo.index.commit(
                f"[checkpoint:{phase.value}] {message}")

            # 构建并返回检查点元数据对象
            checkpoint = CheckpointMeta(
                checkpoint_id=commit.hexsha[:12],
                phase=phase,
                git_commit_hash=commit.hexsha,
                timestamp=time.time(),
                description=message
            )
            return checkpoint
        except Exception as e:
            logger.error(
                f"[Git] Failed to create checkpoint in {worktree_path}: {e}")
            return None

    def soft_rollback(self, worktree_path: str, target_commit_hash: str) -> str:
        """
        软回滚（Soft Rollback）机制
        
        说明：当重构失败需要回退时，不直接覆盖或重置当前分支，
        而是基于当前错误现场切出一个 fork 分支进行保留，
        然后将当前分支 hard reset 到目标检查点的哈希值，以此实现安全的“时间旅行”。
        
        :param worktree_path: 沙箱环境绝对路径
        :param target_commit_hash: 目标回滚位置的 commit hash
        :return: 保存错误现场的 fork 分支名称
        """
        wt_repo = Repo(worktree_path)
        current_branch = wt_repo.active_branch.name

        # 为当前的错误现场创建一个 fork 备份分支
        fork_name = f"{current_branch}-fork-{int(time.time())}"
        wt_repo.git.branch(fork_name)
        
        # 将当前分支重置到目标检查点
        wt_repo.git.reset("--hard", target_commit_hash)

        return fork_name

    def apply_to_main(self, worktree_path: str) -> str:
        """
        将沙箱中的修改合并回主仓库
        
        说明：使用 squash merge 将零碎的检查点提交合并为单个整洁的提交，
        以此保持主仓库历史记录的干净。
        
        :param worktree_path: 沙箱环境绝对路径
        :return: 合并后产生的新 commit hash
        """
        wt_repo = Repo(worktree_path)
        branch_name = wt_repo.active_branch.name

        # 在主仓库上进行 squash 合并
        self.repo.git.merge(branch_name, "--squash")
        # 提交合并结果
        self.repo.index.commit(f"refactor: applied changes from {branch_name}")

        return self.repo.head.commit.hexsha

    def cleanup_worktree(self, task_id: str, keep_days: int = 7):
        """
        清理释放指定任务的 worktree 沙箱环境
        
        :param task_id: 任务唯一标识 UUID
        :param keep_days: 现场保留天数（这里暂未实现按天清理逻辑，目前是立即清理）
        """
        worktree_path = f".refactor-workspaces/{task_id}"
        # 强制移除 worktree
        if os.path.exists(worktree_path):
            self.repo.git.worktree("remove", worktree_path, "--force")

        # 删除对应的分支（包含重构历史）
        branch_name = f"refactor/{task_id}"
        try:
            self.repo.git.branch("-D", branch_name)
        except Exception:
            pass
