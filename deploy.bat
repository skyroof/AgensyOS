@echo off
git add .
git commit -m "Fix WELCOME_TEXT"
git push origin main
ssh root@89.169.47.138 "cd /root/bot && cp .env .env.backup && git stash && git pull && cp .env.backup .env && docker compose down && docker compose up -d --build"
