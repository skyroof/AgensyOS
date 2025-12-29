@echo off
ssh root@89.169.47.138 "cd /root/bot && sed -i 's/ROUTERAI_API_KEY=.*/ROUTERAI_API_KEY=sk-ZCV2rV6RAfeMDiifhE1AW9mfHmVdBET5/' .env && docker compose restart"

