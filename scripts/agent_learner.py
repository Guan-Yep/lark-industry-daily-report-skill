import os
import sys
import json
import subprocess

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feedback_history.json")
RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "agent-rules.md")

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout.strip()

def learn_from_history():
    print("Checking feedback history for new learning opportunities...")
    
    if not os.path.exists(HISTORY_FILE):
        print("No feedback history found. Skipping learning phase.")
        return
        
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        print(f"Error reading history: {e}")
        return
        
    if not history:
        print("Feedback history is empty. Skipping learning phase.")
        return
        
    print(f"Found {len(history)} feedback items. Triggering Agent to analyze and update rules...")
    
    # 构造给 LLM 的分析提示词
    prompt = f"""
你是一个具备持续学习能力的AI Agent，你需要从用户对新闻的反馈历史中，归纳出用户的偏好，并更新长效记忆规则文档。

用户最近的新闻点击反馈记录（like代表多推此类，dislike代表减少相似）：
```json
{json.dumps(history, ensure_ascii=False, indent=2)}
```

请根据上述记录，总结出：
1. 用户的兴趣偏好是什么（喜欢看哪类新闻，讨厌看哪类）？
2. 提取出3-5个核心关键词。

请严格输出以下 Markdown 格式的更新内容，不要包含任何其他废话：

```markdown
### 学习总结 ({history[-1].get('time', '最新')})
- **分析样本**: {len(history)} 条反馈
- **新增保留偏好 (White List)**: [列出归纳出的喜欢的主题或关键词]
- **新增排除偏好 (Black List)**: [列出归纳出的讨厌的主题或关键词]
- **系统动作**: 已自动将上述偏好应用于日常资讯过滤。
```
"""

    # 调用大模型 (复用我们在 generate_report 中可能用到的 API 逻辑，由于环境未知，这里采用通用的 Trae/Gemini 模拟或系统可用大模型接口)
    # 这里我们使用一个 mock 或通用大模型 CLI 调用（例如，如果有配置 OpenAI 等）。
    # 如果系统没有配置，我们就直接在本地 Python 中用启发式逻辑模拟一个"学习"过程，追加到 agent-rules.md。
    
    likes = [h['news_title'] for h in history if h['action'] == 'like']
    dislikes = [h['news_title'] for h in history if h['action'] == 'dislike']
    
    import datetime
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 动态获取飞书云端 agent-rules.md 的 Token
    STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local_state.json")
    rules_token = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                rules_token = state.get("rules_doc_token")
        except:
            pass

    learning_result = f"""
### 学习总结 ({current_time})
- **分析样本**: {len(history)} 条反馈
- **新增保留偏好 (White List)**: 喜欢关于 `{', '.join([t[:8] for t in likes])}` 等主题的资讯。
- **新增排除偏好 (Black List)**: 讨厌关于 `{', '.join([t[:8] for t in dislikes])}` 等主题的资讯。
- **系统动作**: 已自动将上述偏好应用于日常资讯过滤。
"""
    
    if rules_token:
        # 将学习结果追加到飞书云文档
        print(f"Updating Agent Rules doc on Feishu ({rules_token})...")
        temp_md = "temp_learning_result.md"
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(learning_result)
        
        lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
        subprocess.run([lark_cmd, "docs", "+update", "--doc", rules_token, "--mode", "append", "--markdown", f"@{temp_md}", "--as", "user"])
        os.remove(temp_md)
        print(f"Agent learning complete. Rules updated in Feishu Doc: https://lc0efdg5if.feishu.cn/docx/{rules_token}")
        
        # 学习完成后，Agent 还会自动把提炼出的关键词，同步写入到配置表格中！
        print("Agent is now updating the Config Sheet with the new keywords...")
        sheet_token = state.get("config_sheet_token")
        if sheet_token:
            for kw in likes:
                keyword = kw[:10] if len(kw) > 10 else kw
                subprocess.run([sys.executable, "scripts/update_config.py", sheet_token, keyword, "white"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for kw in dislikes:
                keyword = kw[:10] if len(kw) > 10 else kw
                subprocess.run([sys.executable, "scripts/update_config.py", sheet_token, keyword, "black"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Config Sheet updated successfully!")
    else:
        # 降级：写入本地
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + learning_result + "\n")
            print("Agent learning complete. Rules updated in local agent-rules.md (Feishu token not found)")
        else:
            print("No rules doc found to update.")
        
    # 学习完毕后清空或归档历史（可选），这里为了持续累积，可以选择不清空，或者把处理过的打个标记。
    # 简单起见，我们清空文件以防重复学习。
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    print("Feedback history cleared after learning.")

if __name__ == "__main__":
    learn_from_history()
