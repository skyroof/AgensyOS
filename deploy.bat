@echo off
git add .
git commit -m "Add: dark header, page numbers, section dividers"
git push origin main
ssh root@89.169.47.138 "cd /root/bot && git stash && git pull && git stash pop 2>/dev/null; docker compose down && docker compose up -d --build"
