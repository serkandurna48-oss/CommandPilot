# CommandPilot Sandbox — disposable execution environment for the
# claude_code_sandboxed RunnerAdapter
# (scripts/runner_adapters/claude_code_sandboxed.py).
#
# Fixed, checked-in, manually versioned — NEVER pulled from a registry at
# run time, so what actually runs is always exactly what's in this file,
# not whatever a mutable tag happens to point to today. Rebuild after any
# change to this file, from the repo root:
#
#   docker build -t commandpilot-sandbox:latest scripts/sandbox
#
# Full toolchain (Node + Python + git + the `claude` CLI) so this ONE image
# works as a target-repo sandbox for both CommandPilot (Python backend +
# Node frontend) and CampPilot (same stack) — one shared image, chosen over
# maintaining per-repo images.
#
# Runs as root inside the container. The isolation boundary this whole
# adapter's safety argument rests on is the DISPOSABLE git worktree + this
# DISPOSABLE container filesystem (see claude_code_sandboxed.py's module
# docstring) — not a non-root user inside the container. `~/.claude` is
# bind-mounted read-only at /root/.claude by claude_code_sandboxed.py's
# `docker run` invocation, matching that.

FROM node:20-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The same Claude Code CLI claude_code.py drives directly on the host — just
# installed inside the image instead of resolved via shutil.which() from
# PATH. Deliberately unpinned to whatever's current at build time (rebuild
# to update): the whole point of this adapter is running the SAME tool the
# host uses, and Claude Code itself updates frequently.
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /workspace
