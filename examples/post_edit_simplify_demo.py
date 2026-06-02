#!/usr/bin/env python3
"""Demo: watch the post-edit-simplify hook decide when to nudge.

Replays a burst of edits through the hook's pure ``register_edit`` transition and
prints, edit by edit, when the simplicity reminder fires. No Claude Code session,
stdin, or state file needed — this is the classifier in isolation.

Run:  python examples/post_edit_simplify_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "scripts"))

from post_edit_simplify import new_session, register_edit  # noqa: E402

THRESHOLD = 5
COOLDOWN = 600.0  # seconds


def main() -> None:
    edits = [
        ("auth.py", 0.0),
        ("auth.py", 5.0),     # same file again — counted once in the file tally
        ("models.py", 12.0),
        ("views.py", 30.0),
        ("utils.py", 41.0),   # 5th edit -> first reminder is due
        ("utils.py", 90.0),   # within cooldown -> stays quiet
        ("api.py", 700.0),    # past the cooldown -> nudges again
    ]

    session = new_session(0.0)
    print(f"threshold={THRESHOLD} edits, cooldown={int(COOLDOWN)}s\n")
    for path, when in edits:
        reminder = register_edit(session, path, when, threshold=THRESHOLD, cooldown=COOLDOWN)
        tag = "  >> REMIND" if reminder else "          "
        print(f"t={when:6.0f}s  edit #{session['edit_count']}  {path:<11}{tag}")
        if reminder:
            print(f"             {reminder}")

    print(f"\nTotal: {session['edit_count']} edits across "
          f"{len(session['modified_files'])} distinct files.")


if __name__ == "__main__":
    main()
