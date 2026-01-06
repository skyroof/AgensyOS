import os
import sys
import re
import paramiko
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fetch_and_analyze_errors():
    host = os.getenv("SSH_HOST", "89.169.47.138")
    user = os.getenv("SSH_USER", "root")
    password = os.getenv("SSH_PASSWORD")
    
    if not password:
        print("❌ Error: SSH_PASSWORD not found in .env file")
        return

    print(f"🔍 Connecting to {host} to analyze logs...")
    
    try:
        # Create SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            username=user,
            password=password,
            timeout=10
        )
        
        # Fetch last 2000 lines of logs from the bot container
        # We use 'docker logs' directly to avoid some compose formatting noise, 
        # but we need the container name. usually 'bot-bot-1' or similar. 
        # Let's try finding it or using compose logs.
        # 'docker compose logs' is safer if we know the path.
        
        # Check status first
        print("Checking container status...")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && docker compose ps")
        print(stdout.read().decode())
        
        cmd = "cd /root/bot && docker compose logs --tail 2000 --no-log-prefix bot"
        stdin, stdout, stderr = client.exec_command(cmd)
        
        logs = stdout.read().decode('utf-8', errors='ignore')
        error_out = stderr.read().decode('utf-8', errors='ignore')
        
        if error_out and "No such file" in error_out:
            print(f"❌ Error fetching logs: {error_out}")
            return

        # === ANALYSIS ===
        print(f"📊 Analyzed {len(logs.splitlines())} log lines.")
        
        # 1. Find Python Tracebacks
        # Regex to capture "Traceback (most recent call last):" ... until the next non-indented line
        # This is a bit tricky with simple regex, but we can try a heuristic.
        
        traceback_blocks = []
        current_block = []
        in_traceback = False
        
        for line in logs.splitlines():
            if "Traceback (most recent call last):" in line:
                in_traceback = True
                current_block = [line]
            elif in_traceback:
                # If line starts with space/tab or is part of the error message
                if line.startswith(" ") or line.startswith("\t") or "Error:" in line or "Exception:" in line:
                    current_block.append(line)
                else:
                    # End of traceback
                    if current_block:
                        traceback_blocks.append("\n".join(current_block))
                    in_traceback = False
                    current_block = []
        
        # Catch the last block if logs ended with traceback
        if in_traceback and current_block:
            traceback_blocks.append("\n".join(current_block))

        # 2. Find explicit ERROR logs (that might not be tracebacks)
        error_logs = []
        for line in logs.splitlines():
            if "ERROR" in line or "CRITICAL" in line:
                # Skip if it's part of a traceback we already caught (simplified check)
                if not any(line in tb for tb in traceback_blocks):
                    error_logs.append(line)

        # === REPORTING ===
        
        unique_tracebacks = sorted(list(set(traceback_blocks)))
        unique_errors = sorted(list(set(error_logs)))
        
        if not unique_tracebacks and not unique_errors:
            print("✅ No errors found in the last 2000 lines.")
            return

        if unique_tracebacks:
            print(f"\n🔥 Found {len(unique_tracebacks)} unique tracebacks:")
            for i, tb in enumerate(unique_tracebacks, 1):
                print(f"\n--- TRACEBACK #{i} ---")
                print(tb)
                print("---------------------")

        if unique_errors:
            print(f"\n⚠️ Found {len(unique_errors)} other error logs:")
            for i, err in enumerate(unique_errors[-10:], 1): # Show last 10
                print(f"{i}. {err}")

    except Exception as e:
        print(f"\n❌ System Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fetch_and_analyze_errors()
