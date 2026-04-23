import json
import subprocess
import sys

def update_config(sheet_token, keyword, list_type):
    """
    更新飞书云电子表格配置
    list_type: "white" 或 "black"
    """
    lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
    
    try:
        cmd = [lark_cmd, "sheets", "+info", "--url", sheet_token, "--as", "user"]
        res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        info_data = json.loads(res.stdout)
        sheets = info_data.get("data", {}).get("sheets", {}).get("sheets", [])
        
        sheet_id = None
        target_title = "白名单" if list_type == "white" else "黑名单"
        
        for s in sheets:
            if s.get("title") == target_title:
                sheet_id = s.get("sheet_id")
                break
                
        if not sheet_id:
            print(f"Could not find sheet named '{target_title}' in spreadsheet.")
            return
            
        print(f"Appending '{keyword}' to sheet '{target_title}'...")
        # 飞书 sheets +append 命令
        cmd = [lark_cmd, "sheets", "+append", "--url", sheet_token, "--sheet-id", sheet_id, "--values", json.dumps([[keyword]]), "--as", "user"]
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        
        if result.returncode == 0:
            print(f"Successfully added '{keyword}' to {target_title}.")
        else:
            print(f"Failed to update config sheet: {result.stderr}")
            
    except Exception as e:
        print(f"Error updating config sheet: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 3:
        update_config(sys.argv[1], sys.argv[2], sys.argv[3])
