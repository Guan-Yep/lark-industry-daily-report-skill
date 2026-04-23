import subprocess
import json
import sys
import os

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return json.loads(result.stdout)

def main():
    # 1. 尝试使用已有的表，或者创建新表 (假设我们要重命名它)
    spreadsheet_token = "K2mAs80FrhXvKwtKo4KcPFT5nNB"
    lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
    
    print("Fixing spreadsheet title...")
    # 修改标题
    run_cmd([lark_cmd, "api", "patch", f"/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}", "--data", json.dumps({"title": "Agent偏好与信源配置表"}), "--as", "user"])
    
    # 2. 获取现有工作表列表
    print("Fetching existing sheets...")
    res = run_cmd([lark_cmd, "sheets", "+info", "--url", spreadsheet_token, "--as", "user"])
    sheets = res.get("data", {}).get("sheets", {}).get("sheets", [])
    if not sheets:
        print("Failed to get sheets", res)
        return
        
    first_sheet_id = sheets[0]["sheet_id"]
    
    # 3. 修改第一个表的名字为 "信源"
    print("Renaming first sheet...")
    # Actually, it's easier to just add it and not worry about Sheet1, or rename it using sheets_batch_update
    subprocess.run([lark_cmd, "api", "post", f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update", "--data", json.dumps({
        "requests": [{"updateSheet": {"properties": {"sheetId": first_sheet_id, "title": "信源"}}}]
    }), "--as", "user"])
    
    # 4. 添加 "白名单" 和 "黑名单" 表
    print("Adding White and Black lists...")
    requests_data = json.dumps({
        "requests": [
            {"addSheet": {"properties": {"title": "白名单"}}},
            {"addSheet": {"properties": {"title": "黑名单"}}}
        ]
    })
    subprocess.run([lark_cmd, "api", "post", f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update", "--data", requests_data, "--as", "user"])
    
    # 重新获取 sheets 以得到 IDs
    res = run_cmd([lark_cmd, "sheets", "+info", "--url", spreadsheet_token, "--as", "user"])
    sheets = res.get("data", {}).get("sheets", {}).get("sheets", [])
    
    w_id = None
    b_id = None
    for s in sheets:
        if s.get("title") == "白名单": w_id = s.get("sheet_id")
        if s.get("title") == "黑名单": b_id = s.get("sheet_id")
        if s.get("title") == "Sheet1": first_sheet_id = s.get("sheet_id") # in case rename failed
        if s.get("title") == "信源": first_sheet_id = s.get("sheet_id")
    
    # 5. 写入表头和基础数据
    print("Writing headers and data...")
    # 信源表头
    subprocess.run([lark_cmd, "sheets", "+write", "--url", spreadsheet_token, "--sheet-id", first_sheet_id, "--range", "A1:A3", "--values", json.dumps([["信源链接"], ["https://rss.aishort.top/?type=v2ex&node=create"], ["https://rss.aishort.top/?type=36kr&name=newsflashes"]]), "--as", "user"])
    
    # 白名单表头
    if w_id:
        subprocess.run([lark_cmd, "sheets", "+write", "--url", spreadsheet_token, "--sheet-id", w_id, "--range", "A1:A3", "--values", json.dumps([["偏好关键词"], ["大模型"], ["Agent"]]), "--as", "user"])
    if b_id:
        subprocess.run([lark_cmd, "sheets", "+write", "--url", spreadsheet_token, "--sheet-id", b_id, "--range", "A1:A3", "--values", json.dumps([["屏蔽关键词"], ["裁员"], ["财报"]]), "--as", "user"])

    print(f"Successfully initialized config sheet: https://lc0efdg5if.feishu.cn/sheets/{spreadsheet_token}")

if __name__ == "__main__":
    main()
