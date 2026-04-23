import json
import subprocess
import sys
import os

# 读取消息并解析
def main():
    print("Listening for card interactions via lark-event...")
    
    # 我们不仅订阅 card.action.trigger，可能还会收到 im.message.message_read_v1 等其他我们开启了权限但未处理的事件
    # 飞书 CLI 的 event +subscribe 默认会把我们指定的 --event-types 注册上，
    # 但如果之前你还在开发者后台配置了别的信息，飞书也会推过来。
    cmd = [
        "lark-cli.cmd" if sys.platform == "win32" else "lark-cli", 
        "event", "+subscribe", 
        "--event-types", "card.action.trigger,im.message.message_read_v1,im.message.receive_v1", 
        "--compact", "--quiet", "--as", "bot", "--force"
    ]
    
    try:
        # 使用 subprocess.Popen 并在循环中实时读取 stdout
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding='utf-8')
        
        while True:
            line = process.stdout.readline()
            if not line:
                continue
                
            line = line.strip()
            if not line:
                continue
                
            try:
                event_data = json.loads(line)
                
                # event_data 可能是被 compact 扁平化后的字典
                action_value = None
                
                if event_data.get("type") == "card.action.trigger" or "action" in event_data:
                    # 尝试从原事件提取 action -> value
                    if "event" in event_data and "action" in event_data["event"]:
                        action_value = event_data["event"]["action"].get("value")
                    elif "action" in event_data:
                        action_value = event_data["action"].get("value")
                    elif "value" in event_data:
                        action_value = event_data["value"]
                        
                    if isinstance(action_value, str):
                        try:
                            action_value = json.loads(action_value)
                        except:
                            pass
                            
                    if isinstance(action_value, dict) and action_value.get("type") == "feedback":
                        news_title = action_value.get("news_title", "")
                        action_type = action_value.get("action", "") # "like" or "dislike"
                        
                        if news_title:
                            # 为了演示，直接取标题的前半部分
                            keyword = news_title[:10] if len(news_title) > 10 else news_title
                            
                            list_type = "white" if action_type == "like" else "black"
                            print(f"\n[Feedback Received] User clicked '{action_type}' for '{news_title}'")
                            print(f"Adding keyword '{keyword}' to {list_type} list in Feishu Config Sheet...")
                            
                            # 1. 给用户反馈（回复消息）
                            # 在新版卡片事件回调中，消息ID可能在不同的字段中
                            open_message_id = None
                            
                            # 尝试从各种可能的位置提取 open_message_id
                            if "event" in event_data and "context" in event_data["event"]:
                                open_message_id = event_data["event"]["context"].get("open_message_id")
                            
                            if not open_message_id and "context" in event_data:
                                open_message_id = event_data["context"].get("open_message_id")
                                
                            if not open_message_id and "open_message_id" in event_data:
                                open_message_id = event_data["open_message_id"]
                                
                            if not open_message_id and "event" in event_data and "open_message_id" in event_data["event"]:
                                open_message_id = event_data["event"]["open_message_id"]
                                
                            if open_message_id:
                                reply_text = f"✅ 已收到反馈：已将【{keyword}...】加入学习队列，Agent 会在下次更新规律时分析你的偏好！"
                                reply_cmd = [
                                    "lark-cli.cmd" if sys.platform == "win32" else "lark-cli",
                                    "im", "+messages-reply",
                                    "--message-id", open_message_id,
                                    "--content", json.dumps({"text": reply_text}, ensure_ascii=False),
                                    "--msg-type", "text",
                                    "--as", "bot"
                                ]
                                print(f"Sending reply to message {open_message_id}...")
                                import threading
                                def send_reply(cmd):
                                    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
                                    if res.returncode != 0:
                                        print(f"Failed to reply: {res.stderr}")
                                    else:
                                        print("Reply sent successfully.")
                                threading.Thread(target=send_reply, args=(reply_cmd,)).start()
                            else:
                                print(f"Warning: Could not find open_message_id in event data: {event_data.keys()}")
                            
                            # 移除直接更新飞书表格的硬编码逻辑，将其完全交给 agent_learner.py 统一学习和决策
                            # 2. 记录到本地反馈历史中，供 Agent（LLM as Learner）进行深度学习和规则提取
                            history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feedback_history.json")
                            try:
                                if os.path.exists(history_file):
                                    with open(history_file, "r", encoding="utf-8") as hf:
                                        history = json.load(hf)
                                else:
                                    history = []
                            except:
                                history = []
                                
                            import time
                            history.append({
                                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "news_title": news_title,
                                "action": action_type
                            })
                            
                            with open(history_file, "w", encoding="utf-8") as hf:
                                json.dump(history, hf, ensure_ascii=False, indent=2)
                                
                            print(f"Recorded detailed feedback to {history_file}. Agent can learn from this later.")
                            
                    # 卡片回调必须要在 3 秒内响应 200，否则飞书客户端会报 200340 错误。
                    # 如果是通过 lark-cli event 监听，lark-cli 底层会自动响应 200 确认。
                    # 飞书报错 200340 通常是因为你的事件订阅后台没有正确验证长连接，或者处理超时。
                    # 由于我们使用 lark-cli 长连接，它自身会处理心跳和回调响应，但请确保 lark-cli 进程不要阻塞。
                            
            except json.JSONDecodeError:
                pass
                
    except KeyboardInterrupt:
        print("Stopping listener...")
        process.terminate()

if __name__ == "__main__":
    main()