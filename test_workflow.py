import requests
import time
import json
import os

BASE_URL = "http://127.0.0.1:8000/api/v1/refactor"

# 获取绝对路径
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_project"))

def create_task():
    print(f"🚀 创建重构任务 (项目路径: {PROJECT_PATH})...")
    res = requests.post(f"{BASE_URL}/create", json={
        "project_path": PROJECT_PATH,
        "user_request": "Refactor calculateStats to make it cleaner. Extract the logic into separate functions."
    })
    
    if res.status_code != 200:
        print(f"❌ 创建失败: {res.text}")
        exit(1)
        
    data = res.json()
    task_id = data["task_id"]
    print(f"✅ 任务已创建: {task_id}")
    return task_id

def poll_status(task_id):
    print(f"⏳ 轮询任务状态 {task_id}...")
    while True:
        try:
            res = requests.get(f"{BASE_URL}/{task_id}/status")
        except Exception as e:
            print(f"❌ 无法连接到服务: {e}")
            time.sleep(2)
            continue

        if res.status_code != 200:
            print(f"❌ 轮询失败: {res.text}")
            time.sleep(2)
            continue
            
        data = res.json()
        state = data.get("state", {})
        next_nodes = data.get("next", [])
        
        current_phase = state.get("current_phase", "unknown")
        print(f"👉 当前阶段: {current_phase}, 等待节点: {next_nodes}")
        
        if next_nodes:
            print(f"⏸️ 工作流在 {next_nodes} 挂起等待确认...")
            
            if "analyzer" in next_nodes:
                print("\n🧠 [大模型测试1] Planner 已生成规划:")
                print(json.dumps(state.get("subtasks", []), indent=2, ensure_ascii=False))
                user_input = input("\n请输入确认指令 (confirm/modify/replan) [默认 confirm]: ").strip()
                action = user_input if user_input else "confirm"
                requests.post(f"{BASE_URL}/{task_id}/respond", json={"action": action})
                
            elif "refactorer" in next_nodes:
                print("\n📊 [AST分析测试] Analyzer 已生成分析报告:")
                print(json.dumps(state.get("analysis_report", {}), indent=2, ensure_ascii=False))
                user_input = input("\n请输入确认指令 (confirm/add_scope/skip_to_refactor) [默认 skip_to_refactor]: ").strip()
                action = user_input if user_input else "skip_to_refactor"
                requests.post(f"{BASE_URL}/{task_id}/respond", json={"action": action})
                
            elif "code_rewriter" in next_nodes:
                print("\n🤖 [大模型测试2] Refactorer 已生成 RefactorIR:")
                print(json.dumps(state.get("refactor_ir", []), indent=2, ensure_ascii=False))
                user_input = input("\n请输入确认指令 (confirm_all/edit_instructions/regenerate) [默认 confirm_all]: ").strip()
                action = user_input if user_input else "confirm_all"
                requests.post(f"{BASE_URL}/{task_id}/respond", json={"action": action})
                
            elif "validator" in next_nodes:
                print("\n⚙️ [AST执行测试] 重写结果:")
                print(json.dumps(state.get("rewrite_result", {}), indent=2, ensure_ascii=False))
                user_input = input("\n请输入确认指令 (accept/ignore_warnings/redo) [默认 accept]: ").strip()
                action = user_input if user_input else "accept"
                requests.post(f"{BASE_URL}/{task_id}/respond", json={"action": action})
            else:
                user_input = input(f"\n未知节点挂起，请输入确认指令 [默认 confirm]: ").strip()
                action = user_input if user_input else "confirm"
                requests.post(f"{BASE_URL}/{task_id}/respond", json={"action": action})
        
        if current_phase == "completed" or (not next_nodes and current_phase == "failed"):
            print(f"\n🎉 工作流结束! 最终状态: {current_phase}")
            break
            
        time.sleep(3)

if __name__ == "__main__":
    task_id = create_task()
    poll_status(task_id)
