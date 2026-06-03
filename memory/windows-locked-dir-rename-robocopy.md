---
name: windows-locked-dir-rename-robocopy
description: "Windows directory rename failing 'Access/Permission denied' is usually a handle lock (Defender/file-watcher/Explorer/editor); `robocopy SRC DST /E /MOVE` succeeds file-by-file where mv/Rename-Item/Move-Item fail."
metadata: 
  type: feedback
---

On Windows, renaming or moving a *directory* can fail with "Access is denied" / "Permission
denied" even when you own it — a process is holding a handle on the dir or a file inside it
(Windows Defender mid-scan, a file watcher, an open Explorer window, an editor). `mv`,
`Rename-Item`, and `Move-Item` operate at the directory level and fail as a unit.

**Why:** the error reads like a permissions/ACL problem and sends you chasing ownership, but the
real cause is a transient lock; the fix is a tool that works file-by-file. (This kit's own repo
directory was renamed this way.)

**How to apply:** use `robocopy <SRC> <DST> /E /MOVE /R:2 /W:1` — it copies file-by-file then
deletes the source, sidestepping the directory-level lock. Afterwards verify the source is gone and
`.git/` moved intact. If even robocopy is blocked, close the watcher / Explorer / editor holding
the handle first.
