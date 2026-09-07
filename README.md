# 🤖 AI Diff Judge

> An AI that reviews your code changes and tells you, with actual reasoning, whether you made it better or worse.

## 🧠 The idea

Most AI code reviewers just look at one version of your code and say "looks fine 👍".

AI Diff Judge doesn't do that. It looks at the old version and the new version side by side, function by function, and picks a winner with an actual explanation of why. Refactored something? Fixed a bug? Made it worse without noticing? It'll catch it.

This started as my first ever AI/ML project. I had zero experience with LLM APIs, prompt engineering, or building anything beyond basic scripts. A few weeks later this exists, works, comments on real GitHub PRs automatically, and has a measured 87.5% agreement rate with my own human judgment on a benchmark I built myself.

## ⚡ See it in action

Here's an actual comment this bot left on a real Pull Request in this repo.

```
🤖 AI Diff Judge
Comparing main into test diff engine

🔍 chunker.py::extract_functions
Winner: new
"Новая версия добавляет квалифицированные имена, обработку 
синтаксических ошибок и более гибкую структуру, при этом риск 
ошибок и производительность остаются сопоставимыми"

📊 Summary
Old 0, New 3, Tie 0
Overall NEW is better ✅
```

No fake demo. No cherry picked screenshot. It's a real bot comment on a real PR in this repo.

## 🏗️ How it works

```
                    GitHub
                      │
             ┌────────┴────────┐
             │                 │
             ▼                 ▼
        PR mode            Branch mode
     (pr_judge.py)       (branch_judge.py)
             │                 │
             └────────┬────────┘
                      ▼
                 diff_engine.py
              (real git diff parsing)
                      │
                      ▼
                 chunker.py
          (AST based function extraction,
           class aware, syntax error safe)
                      │
                      ▼
                  judge.py
        (Groq LLM compares old vs new,
         returns structured JSON verdict)
                      │
                      ▼
              Voting aggregation
           (old votes vs new votes vs tie)
                      │
                      ▼
              GitHub PR comment
```

The core trick is that instead of dumping an entire file at an LLM and hoping for the best, it finds exactly which functions changed (via real git diff parsing, not just "same name" matching, it's class aware, so ClassA.save() and ClassB.save() never get confused), and judges each one individually. Then it aggregates all those individual verdicts into one overall winner.

## ✨ Features

* Two modes. Review a GitHub Pull Request directly, or compare any two local branches.
* AST based function extraction. Parses your actual code structure, not just text diffs.
* Crash proof. Gracefully skips files with syntax errors instead of dying.
* Class aware matching. No more confusing methods with the same name in different classes.
* Self measured benchmark. 87.5% agreement with human judgment, and growing (see benchmark folder).
* 11 passing tests covering the diff parser, chunker, and judge logic.
* Runs automatically on every PR via GitHub Actions.
* Runs on Groq's free tier, so there are no API costs. See the rate limit warning below before pointing it at a busy repo.

## 🚀 Quick start

Clone the repo and set up your environment.

```bash
git clone https://github.com/heroofkaist/ai-diff-judge.git
cd ai-diff-judge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the virtual environment with `venv\Scripts\activate` instead.

Add your free Groq API key (get one at console.groq.com) to a `.env` file.

```
GROQ_API_KEY=your_key_here
```

Compare two local branches.

```bash
python3 branch_judge.py --base main --head my-feature-branch --judge
```

Review a live GitHub PR.

```bash
python3 pr_judge.py owner/repo 42
```

## 📈 Benchmark

I built my own mini version of an AI judge benchmark, organized into 8 categories (bug fixes, security, performance, readability, edge cases, breaking changes, false improvements, and style only changes). Hand labeled pairs of old and new code, with my own honest opinion on which is better, then measured how often the AI agrees with me.

```bash
python3 run_pairwise_benchmark.py
```

Current result is 23 out of 24, or 95.8%, agreement with human judgment across all categories. Security, bug fixes, performance, and breaking change detection all score 100%. The one remaining disagreement is in the style only category, where the model consistently favors f-strings over string concatenation on efficiency grounds, a defensible position rather than a model error.

## 🔭 Full diff context

Judging a function in complete isolation has a failure mode. The model can flag a false alarm when a function calls something defined elsewhere in the same change, since it has no way to confirm that the called function actually exists. Early versions of this tool hit exactly that, warning that a new `score_code` import might not exist even though it was defined a few lines away in a sibling file within the very same diff.

This mirrors a known challenge in AI based code and video judging generally, closely related to what the WorldReward paper (arXiv 2609.03952) calls "localized evidence", judging a small slice of change accurately without losing the surrounding context that explains it.

Here's the fix. Every changed file's full current source is collected once per run and passed alongside each function as reference material only, so the model can check whether a symbol actually exists somewhere in the diff before flagging it as missing. For example.

```
WITHOUT context
"New calls undefined normalize, causing runtime error." (false positive)

WITH context
"The new function applies strip and lower, which is likely the intended behavior." (correct)
```

This has been confirmed working across files in production. When reviewing this repo's own PRs, the judge correctly recognized helper functions and classes defined in sibling files as part of the same change, instead of flagging them as missing.

**⚠️ Cost and rate limit warning.** Shipping full diff context makes every function judged send a much bigger request than before. Groq's free tier caps `openai/gpt-oss-20b` at 8,000 tokens per request, which is far below the model's real context window. This repo trims context to fit that budget per call, cutting only at whole file boundaries so a function is never handed a broken middle of a file, and it falls back to no context at all if a request still fails. Even so, a PR touching several files burns through Groq's free tier quota noticeably faster than the old isolated function approach did. If you're running this against a busy repo on a free API key, expect to hit rate limits during heavy use. The tool degrades gracefully in that case, falling back to a plain tie or no verdict rather than crashing, but don't lean on it for high volume automated review unless you're on a paid Groq tier.

## 🗺️ Roadmap

* Bigger benchmark dataset.
* Inline diff comments instead of one big summary comment.

## ⭐ Like this project?

If this made you smile, taught you something, or you just want to support a first time solo project, hit the star button up top. It genuinely helps, and it's the easiest way to say "keep going."

## 🛠️ Built with

Python, Groq for free LLM inference, GitHub Actions, and a lot of `git status` plus stubbornness.

## 📄 License

MIT. Do whatever you want with it.
