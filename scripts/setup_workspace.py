import subprocess
import json
import sys
import os

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local_state.json")

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Error parsing JSON from command output: {result.stdout}", file=sys.stderr)
        return {}

def setup_workspace(space_id, parent_node_token):
    lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
    
    # 1. Load current state
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass

    # 2. Check if workspace changed
    if state.get("space_id") == space_id and state.get("parent_node_token") == parent_node_token and state.get("config_sheet_token"):
        print(f"Workspace unchanged. Using existing config sheet: {state.get('config_sheet_token')}")
        return state.get("config_sheet_token")

    print("Workspace changed or first time setup. Initializing new config sheet...")

    # 3. Delete old config sheet if exists
    old_obj_token = state.get("config_sheet_token")
    if old_obj_token:
        print(f"Deleting old config sheet: {old_obj_token}")
        # Using drive API to delete the file, which also unbinds it from wiki
        run_cmd([lark_cmd, "api", "delete", f"/open-apis/drive/v1/files/{old_obj_token}", "--as", "user"])
        
    old_rules_token = state.get("rules_doc_token")
    if old_rules_token:
        print(f"Deleting old rules doc: {old_rules_token}")
        run_cmd([lark_cmd, "api", "delete", f"/open-apis/drive/v1/files/{old_rules_token}", "--as", "user"])

    # 4. Create new config sheet in the specified Wiki node
    print("Creating new config sheet in Wiki...")
    res = run_cmd([lark_cmd, "wiki", "+node-create", "--space-id", space_id, "--parent-node-token", parent_node_token, "--title", "Agent偏好与信源配置表", "--obj-type", "sheet", "--as", "user"])
    
    if not res.get("ok"):
        print(f"Failed to create wiki node: {res}")
        sys.exit(1)
        
    data = res.get("data", {})
    new_obj_token = data.get("obj_token")
    new_node_token = data.get("node_token")
    
    # 4.1 Create agent rules document in the same Wiki node
    print("Creating new Agent rules document in Wiki...")
    res_rules = run_cmd([lark_cmd, "wiki", "+node-create", "--space-id", space_id, "--parent-node-token", parent_node_token, "--title", "Agent选择规律记忆文档", "--obj-type", "docx", "--as", "user"])
    
    new_rules_obj_token = None
    if res_rules.get("ok"):
        new_rules_obj_token = res_rules.get("data", {}).get("obj_token")
        
        # Initialize the rules doc with template
        init_rules_md = """# Agent 选择规律记忆文档

> 此文件由 Agent 在每次生成日报前（或被用户主动要求时）执行"学习规律"流程后自动维护，记录从用户历史行为中归纳出的选择偏好。
> 每次执行学习流程后更新对应章节，作为系统长效记忆（Long-term Memory）。

---

## 1. 资讯筛选规律 (Filtering Rules)

> Agent 学习并填写：哪类资讯的标题/主题应该被重点保留（👍多推此类），哪类应该被丢弃（👎减少相似）

- **保留偏好 (White List)**:
  - 待学习（首次运行学习流程后更新）

- **排除偏好 (Black List)**:
  - 待学习（首次运行学习流程后更新）

---

## 2. 推送类型判断规律 (Categorization Rules)

> Agent 学习并填写：什么特征的新闻适合放入客观事实类速报、话题引导推文或工具产品推荐

| 分类 | 核心特征与用户偏好 | 示例/关键词 |
|---|---|---|
| **客观事实类速报** | 待学习 | - |
| **话题引导推文** | 待学习 | - |
| **工具/产品推荐** | 待学习 | - |

---

## 3. 学习历史 (Learning History)

| 时间 | 分析样本数 | 更新摘要 |
|---|---|---|
| 初始化 | 0 | 初始化规则库 |
"""
        with open("temp_rules.md", "w", encoding="utf-8") as f:
            f.write(init_rules_md)
        
        # Write template to docx
        subprocess.run([lark_cmd, "docs", "+update", "--doc", new_rules_obj_token, "--mode", "append", "--markdown", "@temp_rules.md", "--as", "user"])
        os.remove("temp_rules.md")
    else:
        print(f"Warning: Failed to create rules wiki node: {res_rules}")

    # 5. Initialize the new spreadsheet (add sheets, write headers)
    print("Initializing spreadsheet structure...")
    
    res_info = run_cmd([lark_cmd, "sheets", "+info", "--url", new_obj_token, "--as", "user"])
    sheets = res_info.get("data", {}).get("sheets", {}).get("sheets", [])
    first_sheet_id = sheets[0]["sheet_id"] if sheets else None

    if first_sheet_id:
        subprocess.run([lark_cmd, "api", "post", f"/open-apis/sheets/v2/spreadsheets/{new_obj_token}/sheets_batch_update", "--data", json.dumps({
            "requests": [{"updateSheet": {"properties": {"sheetId": first_sheet_id, "title": "信源"}}}]
        }), "--as", "user"])

    requests_data = json.dumps({
        "requests": [
            {"addSheet": {"properties": {"title": "白名单"}}},
            {"addSheet": {"properties": {"title": "黑名单"}}}
        ]
    })
    subprocess.run([lark_cmd, "api", "post", f"/open-apis/sheets/v2/spreadsheets/{new_obj_token}/sheets_batch_update", "--data", requests_data, "--as", "user"])

    res_info = run_cmd([lark_cmd, "sheets", "+info", "--url", new_obj_token, "--as", "user"])
    sheets = res_info.get("data", {}).get("sheets", {}).get("sheets", [])
    
    w_id = None
    b_id = None
    for s in sheets:
        if s.get("title") == "白名单": w_id = s.get("sheet_id")
        if s.get("title") == "黑名单": b_id = s.get("sheet_id")
        if s.get("title") in ["Sheet1", "信源"]: first_sheet_id = s.get("sheet_id")

    # Write default data
    lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
    
    # Write using --data (which accepts raw JSON string and doesn't get messed up by powershell escaping in subprocess as much if we use strings properly, or better yet, just use the lark-cli without relying on implicit shell escaping)
    # The safest way is to write the JSON to a temp file and use @file.json, or just format the string carefully.
    
    with open("temp_values.json", "w", encoding="utf-8") as f:
        json.dump([["信源链接"], ["https://rss.aishort.top/?type=v2ex&node=create"], ["https://rss.aishort.top/?type=36kr&name=newsflashes"]], f)
    subprocess.run([lark_cmd, "sheets", "+write", "--url", new_obj_token, "--sheet-id", first_sheet_id, "--range", "A1:A3", "--values", "@temp_values.json", "--as", "user"])
    os.remove("temp_values.json")
    
    if w_id:
        with open("temp_values.json", "w", encoding="utf-8") as f:
            json.dump([["偏好关键词"], ["大模型"], ["Agent"]], f, ensure_ascii=False)
        subprocess.run([lark_cmd, "sheets", "+write", "--url", new_obj_token, "--sheet-id", w_id, "--range", "A1:A3", "--values", "@temp_values.json", "--as", "user"])
        os.remove("temp_values.json")
        
    if b_id:
        with open("temp_values.json", "w", encoding="utf-8") as f:
            json.dump([["屏蔽关键词"], ["裁员"], ["财报"]], f, ensure_ascii=False)
        subprocess.run([lark_cmd, "sheets", "+write", "--url", new_obj_token, "--sheet-id", b_id, "--range", "A1:A3", "--values", "@temp_values.json", "--as", "user"])
        os.remove("temp_values.json")

    # 6. Save new state
    state["space_id"] = space_id
    state["parent_node_token"] = parent_node_token
    state["config_sheet_token"] = new_obj_token
    state["config_node_token"] = new_node_token
    if new_rules_obj_token:
        state["rules_doc_token"] = new_rules_obj_token

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"Setup complete.")
    print(f"Config sheet: https://lc0efdg5if.feishu.cn/sheets/{new_obj_token}")
    if new_rules_obj_token:
        print(f"Rules doc: https://lc0efdg5if.feishu.cn/docx/{new_rules_obj_token}")
    return new_obj_token, new_rules_obj_token

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python setup_workspace.py <SPACE_ID> <PARENT_NODE_TOKEN>")
        sys.exit(1)
    setup_workspace(sys.argv[1], sys.argv[2])
