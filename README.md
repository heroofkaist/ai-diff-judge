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
* 100% free. Runs on Groq's free tier, no API costs.

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

I built my own mini version of an AI judge benchmark. Hand labeled pairs of old and new code, with my own honest opinion on which is better, then measured how often the AI agrees with me.

```bash
python3 run_pairwise_benchmark.py
```

Current result is 7 out of 8, or 87.5%, agreement with human judgment. The one disagreement turned out to be a genuinely debatable case, not a model error.

## 🗺️ Roadmap

* Weighted scoring, so a correctness regression outweighs three cosmetic improvements.
* Per criterion breakdown covering correctness, readability, performance, and security.
* Handle files that are renamed and modified at the same time.
* Bigger benchmark dataset.
* Inline diff comments instead of one big summary comment.

## ⭐ Like this project?

If this made you smile, taught you something, or you just want to support a first time solo project, hit the star button up top. It genuinely helps, and it's the easiest way to say "keep going."

## 🛠️ Built with

Python, Groq for free LLM inference, GitHub Actions, and a lot of `git status` plus stubbornness.

## 📄 License

MIT. Do whatever you want with it.
