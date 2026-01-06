import os
import time
import requests
import docker
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID", "785561885") 
CONTAINER_NAME = "diagnostic-bot"
CHECK_INTERVAL = 300  # 5 minutes

def send_telegram_message(text):
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": ADMIN_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        print(f"✅ Sent alert to {ADMIN_ID}")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")

def main():
    print("🚀 Watchdog started (Docker Socket mode)...")
    
    try:
        client = docker.from_env()
    except Exception as e:
        print(f"❌ Failed to connect to Docker: {e}")
        send_telegram_message(f"❌ <b>Watchdog Error</b>\nFailed to connect to Docker Socket: {e}")
        return

    send_telegram_message("🤖 <b>Watchdog перезапущен</b>\nСлежу за логами контейнера через Docker Socket.")
    
    # Начинаем следить с текущего момента
    last_log_time = datetime.now()
    
    while True:
        try:
            container = client.containers.get(CONTAINER_NAME)
            
            # Получаем логи с последнего времени
            logs = container.logs(since=int(last_log_time.timestamp()), stderr=True, stdout=True)
            logs_decoded = logs.decode('utf-8', errors='ignore')
            
            # Обновляем время
            last_log_time = datetime.now()
            
            if not logs_decoded:
                time.sleep(CHECK_INTERVAL)
                continue
                
            lines = logs_decoded.splitlines()
            errors = []
            
            traceback_buffer = []
            in_traceback = False
            
            for line in lines:
                if "Traceback (most recent call last):" in line:
                    in_traceback = True
                    traceback_buffer = [line]
                elif in_traceback:
                    if line.startswith(" ") or line.startswith("\t") or "Error:" in line or "Exception:" in line:
                        traceback_buffer.append(line)
                    else:
                        if traceback_buffer:
                            errors.append("\n".join(traceback_buffer))
                        in_traceback = False
                        traceback_buffer = []
                elif "ERROR" in line or "CRITICAL" in line:
                    if not in_traceback:
                        errors.append(line)
            
            if in_traceback and traceback_buffer:
                errors.append("\n".join(traceback_buffer))
            
            if errors:
                print(f"🔥 Found {len(errors)} new errors")
                unique_errors = sorted(list(set(errors)))
                
                report = f"🔥 <b>Новые ошибки ({len(unique_errors)}):</b>\n\n"
                for i, err in enumerate(unique_errors[:5], 1):
                    err_clean = err.replace("<", "&lt;").replace(">", "&gt;")
                    err_clean = err_clean[:500] + "..." if len(err_clean) > 500 else err_clean
                    report += f"<b>Error #{i}:</b>\n<code>{err_clean}</code>\n\n"
                
                if len(unique_errors) > 5:
                    report += f"<i>...и еще {len(unique_errors) - 5} ошибок.</i>"
                
                send_telegram_message(report)
            else:
                print("✅ No new errors")
            
        except docker.errors.NotFound:
            print(f"❌ Container {CONTAINER_NAME} not found")
        except Exception as e:
            print(f"❌ Error checking logs: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
