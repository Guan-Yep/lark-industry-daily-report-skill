import os
import subprocess
import json
import tempfile

def main():
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "message_card.json")
    user_id = "ou_b8dfab0ad0c6af631ad1f10ace02735e"
    
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
