---
name: ps-here-string-fails-in-bash-tool
description: "PowerShell here-string @'...'@ is not valid in the Bash tool — it silently mangles commit messages / breaks gh --body; pass multi-line args via a file + -F/--body-file."
metadata: 
  type: feedback
---

On a Windows machine where the default shell is PowerShell, the agent context is primed for PowerShell
syntax — but the **Bash tool is POSIX `sh`**. The PowerShell here-string `@'...'@` is NOT a here-string
in bash: `@` is a literal char, `'...'` is an ordinary single-quoted string, and the trailing `@` is
another literal. Using it inside the Bash tool fails *quietly*:

- `git commit -m @'\n...\n'@` produced a commit, but with a stray `@` on the first AND last line of
  the message (needed a `git commit --amend -F <file>` to fix).
- `gh pr create --body @'...backtick...'@` broke with `unexpected EOF while looking for matching
  backtick` — the body's backticks were interpreted by bash, not quoted.

**Why:** it looks like it "works" (the first call even produced a commit), so the corruption is easy
to miss; and the priming toward PowerShell makes the mistake recur. Same fault line as
[[bat-from-agent-use-powershell-not-cmd]] and [[launch-json-env-use-powershell-not-cmd]], but the
INVERSE direction: PowerShell syntax leaking INTO the Bash tool, not calling PS from bash.

**How to apply:** in the Bash tool, never use `@'...'@`. For any multi-line or special-char argument
(commit messages, PR bodies), Write the content to a file first and pass it via the flag that reads a
file — `git commit -F <file>`, `gh pr create --body-file <file>` — or use a real bash heredoc /
`$'...'`. Reserve `@'...'@` for the PowerShell tool only. PowerShell-isms that DON'T apply in the Bash
tool: `@'...'@`, `$env:VAR`, backtick line-continuation, `2>$null`.
