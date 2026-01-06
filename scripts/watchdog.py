import os
import time
import requests
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Используем ID админа из конфига или хардкодим, если нужно конкретному юзеру
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID", "785561885") 

LOG_FILE = "/app/logs/app.log"
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

def analyze_logs(last_position):
    if not os.path.exists(LOG_FILE):
        print(f"⏳ Log file {LOG_FILE} not found yet.")
        return last_position, []

    errors = []
    current_position = last_position

    try:
        # Если файл стал меньше (ротация логов), сбрасываем позицию
        current_size = os.path.getsize(LOG_FILE)
        if current_size < last_position:
            last_position = 0
            
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            # Move to last position
            f.seek(last_position)
            new_data = f.read()
            current_position = f.tell()
            
            if not new_data:
                return current_position, []

            lines = new_data.splitlines()
            
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

    except Exception as e:
        print(f"❌ Error reading logs: {e}")
        
    return current_position, errors

def main():
    print("🚀 Watchdog started...")
    # Ждем появления файла
    retries = 10
    while not os.path.exists(LOG_FILE) and retries > 0:
        print(f"⏳ Waiting for log file... {retries}")
        time.sleep(5)
        retries -= 1
        
    send_telegram_message("🤖 <b>Watchdog запущен</b>\nБуду следить за ошибками каждые 5 минут.")
    
    # Start from end of file to avoid spamming old errors
    if os.path.exists(LOG_FILE):
        last_position = os.path.getsize(LOG_FILE)
    else:
        last_position = 0
        
    while True:
        print(f"🔍 Checking logs... (Pos: {last_position})")
        last_position, new_errors = analyze_logs(last_position)
        
        if new_errors:
            print(f"🔥 Found {len(new_errors)} new errors")
            
            unique_errors = sorted(list(set(new_errors)))
            
            if unique_errors:
                report = f"🔥 <b>Обнаружены ошибки ({len(unique_errors)} уникальных):</b>\n\n"
                for i, err in enumerate(unique_errors[:5], 1):
                    # Escape HTML tags in error message
                    err_clean = err.replace("<", "&lt;").replace(">", "&gt;")
                    err_clean = err_clean[:500] + "..." if len(err_clean) > 500 else err_clean
                    report += f"<b>Error #{i}:</b>\n<code>{err_clean}</code>\n\n"
                
                if len(unique_errors) > 5:
                    report += f"<i>...и еще {len(unique_errors) - 5} ошибок.</i>"
                
                send_telegram_message(report)
        else:
            print("✅ No new errors")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
