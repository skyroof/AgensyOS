@echo off
git add .
git commit -m "Fix WELCOME_TEXT"
git push origin main
ssh root@89.169.47.138 "cd /root/bot && git pull && docker compose down && docker compose up -d --build"

