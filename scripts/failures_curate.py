"""Curate data/failures_full.json (research notes with sources and verbatim quotes, compiled 17 Nov 2026) into the
compact data/failures.json shown on the dashboard's fourth tab.

Rule: only failure evidence from the last six months (sources dated May 2026 or later, about models then at the
frontier). Benchmarks with no such evidence say so in one line. Text here is hand-written from the full notes;
URLs, dates and quotes are taken from the full file by index so they cannot be mistyped.
  F(i) = failure_modes[i], X(i) = examples[i] of the same benchmark in failures_full.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = {b["id"]: b for b in json.load(open(ROOT / "data" / "failures_full.json"))["benchmarks"]}

# id: (one-line description, note or None, examples [(X index, task, model, failure in a few words, detail)],
#      failure types [(F index, label, one line, models)])
HUMAN = {'frontiercode': 'Tasks and grading criteria were written by each repo’s maintainers; no human score is reported.', 'frontierswe': 'No overall human score is reported; on the racing task a skilled human scores about 0.8.', 'posttrainbench': 'No human score is reported. For reference, the same small models’ official instruct versions score 51%.', 'osworld-2': 'People can do these tasks: a median of about 1.6 hours each.', 'chess-puzzles': 'Strong human players (rated 1700–2400) scored 40–75% on a sample.', 'spireclimb': 'Top human players win roughly 85% and 95% of such runs in the two games.', 'frontiermath': 'Every problem was written and vetted by expert mathematicians; no human score is reported.', 'remote-labor-index': 'Every project was completed by a paid human freelancer, and that deliverable is the bar.', 'weirdml-v3': 'No human score is reported.', 'apex-agents': 'Tasks were written by professionals, who estimate 1–2 hours each; no human score is reported.', 'balrog': 'No human score is reported; NetHack takes people years to master.', 'lmca': 'Experts agree with one another at about 85, which is the practical ceiling.'}

CUR = {
 "frontiercode": ("Real pull-request-sized changes in open-source repos, graded on hidden criteria written by each repo’s maintainers: would they merge it? (Cognition)", None,
  [(0, "Mock Service Worker: fix “resetHandlers() doesn’t restart the generator”.", "Claude Opus 5.5 — 0/5 runs at every effort level",
    "Fixed the symptom, missed the implied cleanup", "It drops the old generator on reset, so the reported bug goes away, but the old generator is never closed and the user’s finally-block cleanup never runs."),
   (1, "PostHog Android SDK: fix a startup race that sends events out of order.", "GPT-6 Astra — 5/5 at low effort, 1/5 at max",
    "Over-rewrote and broke the public API", "At max effort it often deletes a public class outright and spreads its job across other files. The race is fixed, but every user of the SDK gets a breaking change.")],
  [(0, "Not thorough", "Fixes what was asked, misses what was implied (sibling code paths, other input types, cleanup). The largest category of failed checks.", "Opus 5.5, Fable 5.1, GPT-6.1 Sol, GPT-6 Astra"),
   (1, "Core behaviour wrong", "The change does not do what the task requires: 14.9% of core-behaviour checks fail at high effort.", "same four models, pooled"),
   (2, "Does too much at high effort", "More thinking means more files rewritten than needed; scores can fall as effort rises.", "Opus 5, Fable 5, GPT-5.6 Sol"),
   (3, "Overthinks into a misreading", "Talks itself into a wrong reading of the request, or fetches the upstream fix (which zeroes the run).", "models on FrontierCode 1.1")]),
 "frontierswe": ("Day-long engineering tasks (build a system, optimise, research), each with up to 20 hours and a hidden clean verifier (Proximal).", None,
  [(0, "Write a driving policy from camera images that laps a racing simulator fast, including unseen tracks.", "Claude Fable 5.2 — 0.35; Claude Opus 5.5 — 0.26",
    "Slower than a simple hand-written bot", "On the task’s scale 0.4 is the benchmark’s own heuristic bot and 0.8 a skilled human. Why is not documented."),
   (1, "Implement a SPICE circuit simulator in Rust that matches reference outputs.", "GPT-5.6 Sol — 33/99 cases",
    "Replayed the visible answers instead of fixing its simulator", "It first called replaying the public gold files unethical, then did it after several cases kept failing. The clean verifier removed the shortcut."),
   (2, "Implement a crash-proof flash filesystem in Zig, to the exact byte layout.", "Muse Spark 1.2 — 0.003",
    "Rewrote the tests to always pass", "Submitted with 87% of its time unused; the clean verifier discarded the harness changes.")],
  [(0, "Edge cases and compatibility", "The core system works; points are lost on edge cases and exact compatibility with the reference.", "Fable 5.1, GPT-5.6 Sol and other launch models"),
   (1, "Optimisations that only help the visible workload", "Speed-ups tuned to the cases the agent can see are penalised on the rest.", "launch models"),
   (2, "Does not find what limits its method", "On research tasks models pick similar recipes; few build an evaluation that shows why the recipe fails.", "launch models"),
   (3, "Ships a shortcut", "Hard-codes or replays answers, or tampers with the checker.", "GPT-5.6 Sol, Muse Spark 1.2"),
   (4, "Stops early or never submits", "Some finish with most of the 20 hours unused; others work until the budget expires without submitting.", "several models")]),
 "posttrainbench": ("An agent gets 10 hours and one GPU to fine-tune a small open model for a target benchmark; score is the trained model’s result.", None,
  [(2, "Post-train Qwen3-1.7B for HumanEval. Consulting earlier PostTrainBench runs is forbidden.", "GPT-5.6 Sol — run flagged",
    "Copied the recipe from earlier runs of the benchmark", "Five minutes in, it cloned the benchmark’s repo, opened the public trace viewer and lifted the data mix and learning-rate schedule."),
   (0, "Post-train Qwen3-1.7B for a writing benchmark. Using the grader’s model API is forbidden.", "GPT-5.5 — scored as the untrained model",
    "Distilled a stronger model through the forbidden API", "Hours in, it used the grader’s API key to generate 2,000 training completions from another model.")],
  [(0, "Little gain on hard targets", "Agents add 47–48 points on easy targets (GSM8K, function calling) but only 6 on AIME.", "leaderboard, Sep 2026"),
   (1, "Narrow search over methods", "Agents start with plain supervised fine-tuning and tune data and hyperparameters; they rarely try another training method.", "general"),
   (3, "Trains on the test questions", "Looks at which test questions the model got wrong and mass-produces near-copies of them.", "GPT-5.5 and others"),
   (2, "Breaks the rules to get data", "Uses a forbidden hosted model to write training data; flagged runs get the base-model score.", "GPT-5.5 and others")]),
 "osworld-2": ("Long computer-use tasks across real desktop apps, up to 500 steps each (XLANG). Epoch’s audit found grading errors in 36 of 50 audited tasks, so some failures are the grader’s.", None,
  [(0, "Compile a purchase-order sheet from requests and approvals arriving by spreadsheet, chat and direct message.", "Model not named (paper discusses GPT-5.5 and Claude Opus 4.7)",
    "Missed approvals that changed mid-task", "It saw the late messages, stopped gathering too early, and checked its sheet against its own incomplete list."),
   (1, "Build a FreeCAD bracket from a mechanical drawing and export it.", "Model not named",
    "Plausible shape, wrong dimensions, no real check", "Its final check was that the file existed, not that the geometry matched the drawing."),
   (2, "File an overseas expense claim with evidence from bank, email and guidelines.", "Model not named",
    "Never submitted", "Still collecting evidence at step 300 of 500; turned to the form only when the budget was nearly gone.")],
  [(0, "Loses track over long tasks", "Agents can click and code; over hundreds of steps they drop constraints and skip checking.", "GPT-5.5, Opus 4.7/4.8"),
   (1, "Stale information", "A message changes the rules mid-task and the agent carries on with the old ones.", "GPT-5.5, Opus 4.7"),
   (2, "Submits without verifying", "Finishes the visible action and stops, even after noticing a problem.", "GPT-5.5, Opus 4.7"),
   (4, "Acts on an old screenshot", "On moving interfaces the click lands where the button used to be.", "screenshot-based agents"),
   (5, "Model-specific styles", "GPT-5.5 bypasses the app and edits files directly (brittle); Opus 4.7 stays in the interface and works without converging.", "GPT-5.5, Opus 4.7")]),
 "chess-puzzles": ("100 chess positions; the model must name the engine’s single best move (Epoch).", None,
  [(2, "The 100 puzzles, re-run by independent auditors on version 1.", "Claude Opus 5.5 — 38% as scored",
    "A content filter blocked 48 of 100 answers", "The provider’s filter flagged the chess analysis as cyber content, and blocked answers count as wrong. On unblocked puzzles it got 79%. It scores 67% on Epoch’s version 2.")],
  [(0, "Near-miss wrong move", "Told only “not the best move” and given one more try, GPT-6 Astra goes from 71% to 87%.", "GPT-6 Astra, Gemini 3.8 Flash"),
   (1, "Safety filter blocks the answer", "Counts as wrong; mainly affects Claude models.", "Opus 5.5, Fable 5")]),
 "spireclimb": ("Win full runs of Slay the Spire 1 and 2 at maximum difficulty through the game’s graphical interface (Epoch).", "No transcripts are public and Epoch has not analysed why individual runs are lost.",
  [(0, "Slay the Spire 1, Ascension 20 with the Heart kill, 60 runs.", "Claude Opus 5.5 — won 5%; GPT-6 Astra — 33%",
    "Loses most runs; cause not documented", "Top human players win at least 80% at this difficulty.")],
  [(1, "Interface mistakes, hurried decisions", "Misclicks still occur, and playing through screenshots may push models to decide quickly.", "models at launch"),
   (3, "Weak with particular characters", "GPT-6.1 Sol does far worse with one character; Epoch could not say why.", "GPT-6.1 Sol")]),
 # no failure evidence from the last six months
 "frontiermath": ("Unpublished research-style maths problems; one exact final answer, no partial credit (Epoch).",
  "No public evidence on how current models fail. The private problems and transcripts are unpublished, and Epoch’s error analyses cover 2025 models only. Claude Opus 5.5 solved 260 of 285 private Tier 1–3 problems (91%). Epoch’s June 2026 audit fixed errors in 42% of problems and ECI treats 95% as the ceiling, so some of the remaining gap may be errors in the benchmark (an inference; Epoch does not explain the 95%).",
  [(0, "Public sample (Tier 1): expected perimeter of the region containing the centre of a regular 101-gon when each diagonal is drawn with probability 0.001.", None, None, None),
   (1, "Public sample (Tier 1): count the nonzero points on x³y + y³z + z³x = 0 over the field with 5¹⁸ elements, up to scaling.", None, None, None)], []),
 "remote-labor-index": ("Real paid freelance projects (design, video, audio, architecture, games, data); a deliverable passes only if a client would accept it (Center for AI Safety, Scale AI).",
  "No public evidence on how current models fail. The only failure breakdown is from the October 2025 paper, when the best agent passed 2.5%; Claude Fable 5.2 now passes 41% and Opus 5.5 21%, and nothing has been published about their rejected work.",
  [(0, "Re-render a ring design with a marquise-cut diamond in place of the emerald-cut one, from a reference photo.", None, None, None),
   (1, "Make 3D product animations showing the features of a new earbuds design and its case.", None, None, None),
   (2, "Arrange “Singing in the Rain” for seven parts for a small house concert.", None, None, None)], []),
 "weirdml-v3": ("Unusual machine-learning tasks where the agent is given unexplained arrays and little or no feedback (Håvard Ihle).",
  "No failure analysis has been published; only the task designs are public.",
  [(0, "A thousand unlabelled point clouds: work out that they are five shapes, then classify sparser and noisier ones.", None, None, None),
   (2, "Turn raw data from a simulated radio telescope into a sky map, without ever seeing a score.", None, None, None)], []),
 "apex-agents": ("Multi-step professional-services tasks (banking, consulting, law) in a simulated workplace (Mercor).",
  "No recent failure evidence. The paper’s analysis is from January 2026, when the best model passed 24%; the top score is now 84%.",
  [(0, "Report a company’s P/E ratio from the implied share price in a DCF model and diluted EPS in the annual financials.", None, None, None)], []),
 "balrog": ("Six text-and-grid games, from simple grid worlds to NetHack.",
  "No recent failure evidence; the paper’s analysis covers 2024 models. In current data almost all the missing score is NetHack, where the best model (GPT-6 Astra) reaches 13% progress.", [], []),
 "lmca": ("Rate how well a critique answers a philosophical position; scored against expert ratings (Redwood Research).",
  "No failure evidence on current models; the paper’s worked failures are from Claude Opus 4 (2025). The authors put the ceiling near 85% because experts disagree on some items.", [], []),
}

out = []
for bid, (what, note, exs, modes) in CUR.items():
    f = FULL[bid]
    out.append(dict(
        id=bid, title=f["title"].split(" (")[0], eci_names=f["eci_names"], what=what, human=HUMAN[bid], note=note,
        examples=[dict(task=t, model=m, fail=fl, detail=d, url=f["examples"][i].get("source_url") or f["examples"][i].get("task_url")) for i, t, m, fl, d in exs],
        modes=[dict(label=l, desc=d, about=a, date=f["failure_modes"][i].get("source_date"), url=f["failure_modes"][i]["source_url"]) for i, l, d, a in modes],
        links=f.get("links", [])[:4]))
json.dump(dict(retrieved="2026-11-17", cutoff="2026-05", benchmarks=out), open(ROOT / "data" / "failures.json", "w"), ensure_ascii=False, indent=1)
print("wrote data/failures.json:", len(out), "benchmarks,", sum(bool(b["modes"]) for b in out), "with recent failure evidence")
