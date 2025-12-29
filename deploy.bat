@echo off
git add .
git commit -m "Premium PDF update" 2>nul
git push origin main
ssh root@89.169.47.138 "cd /root/bot && git stash && git pull && git stash pop 2>/dev/null; docker compose down && docker builder prune -f && docker compose up -d --build --no-cache"
