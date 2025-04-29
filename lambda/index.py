# lambda/index.py
import json
import os
import urllib.request

# 基本設定
FASTAPI_URL = os.environ.get(
    "FASTAPI_URL",        # 環境変数があったら対応するが、APIずっと起動できないので、ここで設定
    "https://7b22-34-126-163-104.ngrok-free.app"   # FastAPI の URL を指定
).rstrip("/")             # 末尾に / が来ても揃うようにした

ENDPOINT = f"{FASTAPI_URL}/generate"
TIMEOUT  = 60             # / s

def make_prompt(history, newest):
    """Bedrockの会話履歴を 1 本のプロンプト文字列に整形し FastAPI へ送る工程"""
    buf = ["こんちゃーす\n"]
    for m in history:
        role = "ユーザー" if m["role"] == "user" else "アシスタント"
        buf.append(f"{role}: {m['content']}\n")
    buf.append(f"ユーザー: {newest}\nアシスタント: ")
    return "".join(buf)

def call_fastapi(prompt: str) -> str:
    """FastAPI /generate に POST し、generated_text を返す工程"""
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"prompt": prompt}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
    return json.loads(raw.decode())["generated_text"].strip()

# ------------------- Lambda ハンドラー -------------------
def lambda_handler(event, context):
    print("Received event:", json.dumps(event))                 # デバッグ用

    # Cognito ユーザーが付与されていればログに残す
    if (u := event.get("requestContext", {}).get("authorizer", {}).get("claims")):
        print(f"Authenticated user: {u.get('email') or u.get('cognito:username')}")

    # リクエスト
    body = json.loads(event["body"])
    user_msg = body["message"]
    history  = body.get("conversationHistory", [])

    # 会話履歴をまとめて 1 プロンプトに
    prompt = make_prompt(history, user_msg)
    print("Prompt for FastAPI:", prompt[:120], "...")           # 長い場合は冒頭のみ

    # 推論の呼び出し
    assistant_reply = call_fastapi(prompt)
    print("Assistant reply:", assistant_reply[:120], "...")

    # 履歴を更新
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": assistant_reply})

    # レスポンス返却
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps({
            "success": True,
            "response": assistant_reply,
            "conversationHistory": history
        })
    }

