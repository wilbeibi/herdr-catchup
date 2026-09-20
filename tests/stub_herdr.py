#!/usr/bin/env python3
"""A herdr that does what a test tells it to.

Every behaviour relay depends on -- who a name resolves to, what lives in a
pane, and whether a prompt is accepted -- is read from STUB_STATE on each call,
so a test can restart the server, recycle a pane, or unblock an agent between
two relay invocations.
"""
import json
import os
import pathlib
import sys

state = pathlib.Path(os.environ["STUB_STATE"])
d = json.loads(state.read_text())
argv = sys.argv[1:]


def err(code):
    sys.stderr.write(json.dumps({"error": {"code": code, "message": code}}))
    sys.exit(1)


if argv[:2] == ["agent", "get"]:
    agent = d["agents"].get(argv[2])
    if not agent:
        err("agent_not_found")
    print(json.dumps({"result": {"agent": agent}}))
elif argv[:2] == ["agent", "prompt"]:
    target = argv[2]
    fail = d.get("fail", [])
    if "*" in fail or target in fail:
        err(d.get("fail_code", "agent_blocked"))
    log = pathlib.Path(d["log"])
    entries = json.loads(log.read_text()) if log.exists() else []
    entries.append({"target": target, "text": argv[3]})
    log.write_text(json.dumps(entries))
    print(json.dumps({"result": {"agent": {"pane_id": target}}}))
else:
    err("unknown_command")
