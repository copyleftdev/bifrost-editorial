#!/usr/bin/env bash
# Self-contained failover traffic run: v1 mocks, kill 9001 at ~request 15.
set -u
cd /home/ops/Project/bifrost-editorial/bench
fuser -k 9001/tcp 9002/tcp 2>/dev/null; sleep 1
NAME=provider-openai PORT=9001 python3 mock_provider.py > m1.log 2>&1 &
P1=$!
NAME=provider-anthropic PORT=9002 python3 mock_provider.py > m2.log 2>&1 &
P2=$!
sleep 1
python3 traffic.py gateway-failover > gateway-failover-agg.json 2>&1 &
T=$!
sleep 3          # v1 mocks answer in ~1ms; traffic has already hit ~dozens by now
kill $P1 2>/dev/null
wait $T
cat gateway-failover-agg.json
