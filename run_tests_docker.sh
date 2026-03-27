#!/usr/bin/env bash
set -e

BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}=== SmilePreview Backend - Docker Test Runner ===${RESET}\n"

# 1. Build and start services
echo -e "${BOLD}[1/5] Building and starting Docker services...${RESET}"
docker compose up -d --build --wait 2>&1

echo -e "${GREEN}Services running.${RESET}\n"

# 2. Install test dependencies inside the container
echo -e "${BOLD}[2/5] Installing test dependencies...${RESET}"
docker compose exec app pip install --quiet pytest pytest-asyncio httpx 2>&1

# 3. Run pytest with verbose + JUnit XML
echo -e "\n${BOLD}[3/5] Running test suite...${RESET}\n"
docker compose exec app pytest tests/ \
  -v \
  --tb=short \
  --junitxml=/app/test-results.xml \
  --no-header \
  -q 2>&1 || true

# 4. Copy results and generate report
echo -e "\n${BOLD}[4/5] Generating endpoint test report...${RESET}\n"
docker compose cp app:/app/test-results.xml ./test-results.xml 2>/dev/null || true

if [ -f test-results.xml ]; then
  python3 tests/generate_report.py test-results.xml
else
  echo -e "${RED}No test results found. Check test output above for errors.${RESET}"
fi

# 5. Tear down
echo -e "\n${BOLD}[5/5] Tearing down Docker services...${RESET}"
docker compose down -v 2>&1

echo -e "\n${GREEN}${BOLD}Done.${RESET}"
