import os
import subprocess
import json
import tempfile
import sys

def _is_pid_running(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            return str(pid) in r.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def ensure_feedback_listener(base_dir):
    """
    默认守护启动：发送卡片前确保监听服务在线。
    """
    pid_file = os.path.join(base_dir, ".listener.pid")
    listener_script = os.path.join(base_dir, "scripts", "listen_feedback.py")
    if not os.path.exists(listener_script):
        print("Warning: listen_feedback.py not found, skip listener bootstrap.")
        return

    existing_pid = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r", encoding="utf-8") as f:
                existing_pid = int(f.read().strip())
        except Exception:
            existing_pid = None

    if existing_pid and _is_pid_running(existing_pid):
        print(f"Feedback listener is already running (PID={existing_pid}).")
        return

    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            proc = subprocess.Popen(
                [sys.executable, listener_script],
                cwd=base_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, listener_script],
                cwd=base_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
        print(f"Started feedback listener in daemon mode (PID={proc.pid}).")
    except Exception as e:
        print(f"Warning: failed to auto-start feedback listener: {e}")

def main():
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "message_card.json")
    user_id = "ou_b8dfab0ad0c6af631ad1f10ace02735e"
    
    # 默认守护启动：先保证回调监听在线，再发卡片
    ensure_feedback_listener(base_dir)

    with open(json_path, 'r', encoding='utf-8') as f:
        json_content = f.read()

    # Create a temporary JSON file to avoid escaping issues in PowerShell
    temp_json_path = os.path.join(base_dir, "temp_card_payload.json")
    with open(temp_json_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Let's bypass powershell completely and use python subprocess
    import json
    with open(temp_json_path, "r", encoding="utf-8") as f:
        # Load and dump again to ensure it's a tight JSON string
        card_dict = json.load(f)
        card_str = json.dumps(card_dict, ensure_ascii=False)
        
    cmd = [
        "lark-cli.cmd" if os.name == 'nt' else "lark-cli",
        "api", "post", "/open-apis/im/v1/messages",
        "--params", f'{{"receive_id_type":"open_id"}}',
        "--data", json.dumps({"receive_id": user_id, "msg_type": "interactive", "content": card_str}, ensure_ascii=False),
        "--as", "bot"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, text=True, encoding='utf-8')
        print("Success:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Failed:")
        print(e.stderr)
        print(e.stdout)

if __name__ == "__main__":
    main()
