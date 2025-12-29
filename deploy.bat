@echo off
git add .
git commit -m "Fix: add DejaVu fonts for Cyrillic PDF support"
git push origin main
ssh root@89.169.47.138 "cd /root/bot && git stash && git pull && git stash pop && docker compose down && docker compose up -d --build"
