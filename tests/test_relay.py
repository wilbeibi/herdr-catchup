#!/usr/bin/env python3
"""The failure matrix for bin/relay.py.

A clean two-agent demo is the weakest evidence about this code: every path that
matters -- refused delivery, a reply nobody hears, a recycled pane, a thread
cancelled mid-flight -- is untouched by the happy path. These run against a
stubbed herdr and an injected clock so each of them can be made to happen on
purpose.

    python3 tests/test_relay.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
RELAY = str(HERE.parent / "bin" / "relay.py")
STUB = str(HERE / "stub_herdr.py")
T0 = 1_700_000_000.0


def agent(pane, kind, name=None, session="s1", status="idle"):
    return {"pane_id": pane, "name": name, "agent": kind, "agent_status": status,
            "cwd": "/tmp", "agent_session": {"value": session}}


class RelayCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="relay-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_file = self.tmp / "stub.json"
        self.log = self.tmp / "prompts.json"
        self.stub = {
            "agents": {
                "w1:pA": agent("w1:pA", "claude"),
                "w1:pB": agent("w1:pB", "codex", name="reviewer"),
                "reviewer": agent("w1:pB", "codex", name="reviewer"),
            },
            "fail": [], "log": str(self.log),
        }
        self.write_stub()
        self.note = self.tmp / "note.md"
        self.note.write_text("the proposal\n")
        self.answer = self.tmp / "answer.md"
        self.answer.write_text("the critique\n")
        self.clock = T0

    def write_stub(self):
        self.state_file.write_text(json.dumps(self.stub))

    def env(self, pane="w1:pA"):
        e = dict(os.environ)
        e.update(HERDR_BIN_PATH=STUB, STUB_STATE=str(self.state_file),
                 HERDR_CATCHUP_STATE=str(self.tmp / "state"), RELAY_NOW=str(self.clock))
        if pane:
            e["HERDR_PANE_ID"] = pane
        else:
            e.pop("HERDR_PANE_ID", None)
        return e

    def relay(self, *args, pane="w1:pA"):
        r = subprocess.run([sys.executable, RELAY, *args], capture_output=True, text=True,
                           env=self.env(pane))
        self.assertTrue(r.stdout.strip(), f"no JSON on stdout: {r.stderr}")
        return r.returncode, json.loads(r.stdout)

    def ask(self, **kw):
        args = ["ask", "--to", kw.pop("to", "reviewer"), "--note-file", str(self.note)]
        for k, v in kw.items():
            args += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
        return self.relay(*args)

    def threads_root(self):
        return self.tmp / "state" / "threads"

    def manifest(self, tid):
        return json.loads((self.threads_root() / tid / "thread.json").read_text())

    def prompts(self):
        return json.loads(self.log.read_text()) if self.log.exists() else []


class TestDeliveryFailure(RelayCase):
    def test_failed_ask_is_durable_retryable_and_consumes_no_round(self):
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask(mode="debate", max_rounds=4)
        self.assertEqual(rc, 3, out)                      # undelivered, not refused
        self.assertEqual(out["delivery"], "failed")
        self.assertEqual(out["code"], "agent_blocked")
        tid, mid = out["thread"], out["message"]

        d = self.manifest(tid)
        m = d["messages"][0]
        self.assertTrue((self.threads_root() / tid / m["payload"]).exists())
        self.assertIsNone(m["deadline"], "a delivery that never landed must not open a reply window")
        self.assertEqual(self.prompts(), [])

        # A second ask is the wrong recovery: it would invent a second round
        # for a peer that has seen neither.
        rc2, out2 = self.ask(thread=tid)
        self.assertEqual(rc2, 1)
        self.assertEqual(out2["error"], "request_outstanding")
        self.assertEqual(out2["fix"], f"relay.py retry {mid}")

        envelope_before = m["envelope"]
        self.stub["fail"] = []
        self.write_stub()
        rc3, out3 = self.relay("retry", mid)
        self.assertEqual(rc3, 0, out3)
        self.assertEqual(out3["delivery"], "accepted")
        self.assertEqual(out3["attempts"], 2)
        after = self.manifest(tid)["messages"][0]
        self.assertEqual(after["envelope"], envelope_before, "retry must replay, not re-render")
        self.assertIsNotNone(after["deadline"], "the reply window opens on the accepted attempt")
        self.assertEqual(len(self.prompts()), 1)

    def test_reply_notification_failure_keeps_the_answer(self):
        rc, out = self.ask(mode="debate", max_rounds=4)
        self.assertEqual(rc, 0, out)
        mid = out["message"]

        self.stub["fail"] = ["w1:pA"]
        self.write_stub()
        rc2, out2 = self.relay("reply", mid, "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc2, 3, out2)
        self.assertEqual(out2["acked"], mid)
        self.assertEqual(out2["notified"], "failed")

        d = self.manifest(out["thread"])
        self.assertEqual(d["messages"][0]["answered_by"], out2["message"])
        self.assertTrue((self.threads_root() / out["thread"] / d["messages"][1]["payload"]).exists())

        _, st = self.relay("status", out["thread"])
        reasons = {a["reason"] for a in st["needs_attention"]}
        self.assertIn("delivery_failed", reasons)

        self.stub["fail"] = []
        self.write_stub()
        rc3, out3 = self.relay("retry", out2["message"])
        self.assertEqual(rc3, 0, out3)
        _, st2 = self.relay("status", out["thread"])
        self.assertEqual([a["reason"] for a in st2["needs_attention"]], ["awaiting_reply"],
                         "retry clears the failed delivery; the answer is now the open request")


class TestRounds(RelayCase):
    def test_debate_alternates_and_stops_at_max_rounds(self):
        rc, out = self.ask(mode="debate", max_rounds=2)
        tid, m1 = out["thread"], out["message"]
        self.assertEqual(out["round"], 1)

        rc, out2 = self.relay("reply", m1, "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc, 0, out2)
        self.assertTrue(out2["continues"], "debate hands the answer back as the next request")
        self.assertEqual(out2["round"], 2)
        self.assertEqual(out2["thread_state"], "open")

        rc, out3 = self.relay("reply", out2["message"], "--file", str(self.answer), pane="w1:pA")
        self.assertEqual(rc, 0, out3)
        self.assertFalse(out3["continues"], "the last round is answerable but does not extend")
        self.assertEqual(out3["thread_state"], "done")

        self.assertEqual([p["target"] for p in self.prompts()], ["w1:pB", "w1:pA", "w1:pB"])
        self.assertIn("kind=notice", self.prompts()[-1]["text"])

    def test_ask_mode_notifies_the_asker_and_closes(self):
        rc, out = self.ask(mode="ask")
        rc, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc, 0, out2)
        self.assertFalse(out2["continues"])
        self.assertEqual(out2["thread_state"], "done")
        # The one-way version of this is what run.sh already does; the point of
        # a thread is that the asker hears back.
        self.assertEqual(self.prompts()[-1]["target"], "w1:pA")
        self.assertIn("Your peer answered", self.prompts()[-1]["text"])

    def test_late_reply_lands_but_does_not_resume_the_debate(self):
        rc, out = self.ask(mode="debate", max_rounds=4, timeout_min=30)
        self.clock = T0 + 31 * 60
        rc2, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc2, 0, out2)
        self.assertTrue(out2["late"])
        self.assertFalse(out2["continues"], "a requester who gave up should not be re-entered silently")
        self.assertEqual(out2["thread_state"], "done")
        self.assertEqual(self.prompts()[-1]["target"], "w1:pA")

        rc3, out3 = self.ask(thread=out["thread"])
        self.assertEqual(rc3, 1)
        self.assertEqual(out3["error"], "thread_done")

    def test_expired_request_is_flagged_before_it_is_answered(self):
        rc, out = self.ask(timeout_min=30)
        self.clock = T0 + 31 * 60
        _, st = self.relay("status", out["thread"])
        self.assertEqual([a["reason"] for a in st["needs_attention"]], ["request_expired"])


class TestIdentity(RelayCase):
    def test_reply_from_the_wrong_pane_is_refused(self):
        rc, out = self.ask()
        rc2, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pA")
        self.assertEqual(rc2, 1)
        self.assertEqual(out2["error"], "wrong_recipient")
        self.assertIsNone(self.manifest(out["thread"])["messages"][0]["answered_by"])

    def recycle_pB(self):
        """herdr restarted and handed w1:pB to a different agent."""
        self.stub["agents"]["w1:pB"] = agent("w1:pB", "opencode", name="reviewer")
        self.stub["agents"]["reviewer"] = self.stub["agents"]["w1:pB"]
        self.write_stub()

    def test_retry_refuses_to_type_into_a_recycled_pane(self):
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask()
        self.assertEqual(rc, 3)

        self.stub["fail"] = []
        self.recycle_pB()
        rc2, out2 = self.relay("retry", out["message"])
        self.assertEqual(rc2, 3)
        self.assertEqual(out2["code"], "peer_recycled")
        self.assertEqual(self.prompts(), [], "nothing may be typed into a stranger's pane")

    def test_a_recycled_pane_cannot_answer_a_delivered_request(self):
        rc, out = self.ask()
        self.assertEqual(rc, 0, out)
        self.recycle_pB()
        rc2, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc2, 1)
        self.assertEqual(out2["error"], "peer_recycled")
        self.assertIsNone(self.manifest(out["thread"])["messages"][0]["answered_by"])

    def test_an_undelivered_request_cannot_be_answered_at_all(self):
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask()
        self.assertEqual(rc, 3)
        rc2, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc2, 1)
        self.assertEqual(out2["error"], "not_delivered",
                         "a peer that never saw the request cannot be the one answering it")

    def test_compaction_changes_the_session_without_breaking_the_thread(self):
        rc, out = self.ask(mode="debate", max_rounds=4)
        self.stub["agents"]["w1:pB"] = agent("w1:pB", "codex", name="reviewer", session="s2")
        self.stub["agents"]["reviewer"] = self.stub["agents"]["w1:pB"]
        self.write_stub()
        rc2, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc2, 0, out2)   # /clear must not be fatal to a thread

    def test_unresolvable_target_leaves_nothing_behind(self):
        rc, out = self.ask(to="ghost")
        self.assertEqual(rc, 1)
        self.assertEqual(out["error"], "agent_not_found")
        self.assertFalse(self.threads_root().exists())

    def test_self_target_is_refused(self):
        rc, out = self.ask(to="w1:pA")
        self.assertEqual(rc, 1)
        self.assertEqual(out["error"], "self_target")


class TestDerivedRoles(RelayCase):
    def test_a_continuing_debate_message_is_both_answer_and_request(self):
        rc, out = self.ask(mode="debate", max_rounds=2)
        rc, out2 = self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        _, st = self.relay("status", out["thread"])
        self.assertEqual([m["roles"] for m in st["messages"]], [["request"], ["answer", "request"]])
        # A stored role would have said "answer" here and gone stale the moment
        # the debate continued.
        self.assertNotIn("kind", self.manifest(out["thread"])["messages"][1])

    def test_a_terminal_answer_is_only_an_answer(self):
        rc, out = self.ask(mode="ask")
        self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        _, st = self.relay("status", out["thread"])
        self.assertEqual([m["roles"] for m in st["messages"]], [["request"], ["answer"]])


class TestDiagnostics(RelayCase):
    def test_a_blocked_peers_status_reaches_the_human(self):
        self.stub["agents"]["w1:pB"] = agent("w1:pB", "codex", name="reviewer", status="blocked")
        self.stub["agents"]["reviewer"] = self.stub["agents"]["w1:pB"]
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask()
        self.assertEqual(rc, 3)
        detail = self.manifest(out["thread"])["messages"][0]["delivery"]["detail"]
        self.assertIn("peer status: blocked", detail,
                      "otherwise 'retry' is the only thing the human is ever told")

    def test_a_changed_peer_session_is_recorded_not_refused(self):
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask()
        self.assertEqual(rc, 3)

        # the peer hit its limit and a fresh session took the pane
        self.stub["agents"]["w1:pB"] = agent("w1:pB", "codex", name="reviewer", session="s9")
        self.stub["agents"]["reviewer"] = self.stub["agents"]["w1:pB"]
        self.stub["fail"] = []
        self.write_stub()

        rc2, out2 = self.relay("retry", out["message"])
        self.assertEqual(rc2, 0, "refusing here would kill the thread; there is no rebind command")
        self.assertEqual(out2["peer_session_changed"], {"addressed": "s1", "found": "s9"})
        self.assertEqual(len(self.prompts()), 1)

    def test_the_notice_envelope_disowns_the_file_it_points_at(self):
        rc, out = self.ask(mode="ask")
        self.relay("reply", out["message"], "--file", str(self.answer), pane="w1:pB")
        self.assertIn("not instructions addressed to you", self.prompts()[-1]["text"])


class TestCancel(RelayCase):
    def test_cancel_stops_reply_and_retry_but_keeps_artifacts(self):
        rc, out = self.ask(mode="debate", max_rounds=4)
        tid, mid = out["thread"], out["message"]
        payload = self.threads_root() / tid / self.manifest(tid)["messages"][0]["payload"]

        rc2, _ = self.relay("cancel", tid)
        self.assertEqual(rc2, 0)

        rc3, out3 = self.relay("reply", mid, "--file", str(self.answer), pane="w1:pB")
        self.assertEqual(rc3, 1)
        self.assertEqual(out3["error"], "thread_cancelled")
        rc4, out4 = self.relay("retry", mid)
        self.assertEqual(rc4, 1)
        self.assertEqual(out4["error"], "thread_cancelled")
        self.assertTrue(payload.exists(), "cancelling must not destroy the record")


class TestInput(RelayCase):
    def test_a_target_name_can_never_become_a_path(self):
        rc, out = self.ask(to="../../escaped")
        self.assertEqual(rc, 1)
        self.assertEqual(out["error"], "bad_target")
        self.assertFalse(self.threads_root().exists())

    def test_a_thread_id_can_never_become_a_path(self):
        rc, out = self.ask(thread="../../escaped")
        self.assertEqual(rc, 1)
        self.assertEqual(out["error"], "bad_thread_id")
        self.assertFalse((self.tmp / "state" / "escaped").exists())

    def test_reading_an_unknown_thread_creates_nothing(self):
        rc, out = self.relay("status", "T-deadbeef")
        self.assertEqual(rc, 1)
        self.assertEqual(out["error"], "unknown_thread")
        self.assertFalse((self.threads_root() / "T-deadbeef").exists())

    def test_list_is_empty_before_anything_exists(self):
        rc, out = self.relay("list")
        self.assertEqual(rc, 0)
        self.assertEqual(out["threads"], [])


class TestConcurrency(RelayCase):
    def test_parallel_retries_do_not_lose_an_update(self):
        self.stub["fail"] = ["w1:pB"]
        self.write_stub()
        rc, out = self.ask()
        self.assertEqual(rc, 3)
        mid = out["message"]

        procs = [subprocess.Popen([sys.executable, RELAY, "retry", mid],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  env=self.env()) for _ in range(10)]
        for p in procs:
            p.wait()

        d = self.manifest(out["thread"])           # parses => never half-written
        self.assertEqual(d["messages"][0]["delivery"]["attempts"], 11,
                         "every attempt must survive; a lost read-modify-write drops one")

    def test_a_reader_never_blocks_or_mutates(self):
        rc, out = self.ask()
        before = (self.threads_root() / out["thread"] / "thread.json").read_bytes()
        for _ in range(3):
            self.relay("status", out["thread"])
            self.relay("list")
        self.assertEqual((self.threads_root() / out["thread"] / "thread.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
