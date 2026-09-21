"""Turn a Python file into Chrome-extension keystroke actions that survive Monaco's auto-indent.

Measured on 2026-09-16 in the QuantConnect IDE: a Return key event copies the previous
line's indentation exactly (nothing extra after a colon). So each line is typed stripped,
after Tab / shift+Tab presses that move from the previous line's indent to this line's.
"""
import json, sys
tab = int(sys.argv[2])
lines = open(sys.argv[1]).read().rstrip("\n").split("\n")
actions = []
prev = 0
for i, line in enumerate(lines):
    stripped = line.lstrip(" ")
    want = (len(line) - len(stripped)) // 4 if stripped else prev
    delta = want - prev
    if delta < 0:
        actions.append({"name": "computer", "input": {"action": "key", "text": "shift+Tab", "repeat": -delta, "tabId": tab}})
    elif delta > 0:
        actions.append({"name": "computer", "input": {"action": "key", "text": "Tab", "repeat": delta, "tabId": tab}})
    if stripped:
        actions.append({"name": "computer", "input": {"action": "type", "text": stripped, "tabId": tab}})
    if i < len(lines) - 1:
        actions.append({"name": "computer", "input": {"action": "key", "text": "Return", "tabId": tab}})
    prev = want
print(json.dumps(actions))
