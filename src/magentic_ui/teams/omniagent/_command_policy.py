"""Command classifiers for bash and file-tool approval.

**Design principle**: the classifier favors *false positives* (prompting
for a safe command) over *false negatives* (silently executing a
dangerous one).  A minor annoyance — clicking Approve on ``grep rm
file.txt`` — is acceptable; missing a real ``rm -rf /`` is not.
Regex-based pattern matching on the full command string is intentionally
simple and will occasionally match command *arguments* that look like
dangerous command names (e.g. ``grep rm``).  This is by design.

This module provides two classifiers consumed by
``_omni_agent._check_tool_approval()`` under the
``require_approval_untrusted`` policy:

:func:`classify_bash_command`
    Classifies a bash command string by command name and flags.
    **Does not** inspect sandbox type or file paths — paths embedded
    in free-form shell strings may involve variable expansion, globs,
    or subshells, making static extraction unreliable.

    - ALLOW: strictly read-only, no-side-effect commands
    - REQUIRE_APPROVAL: mutations, network access, code execution
    - DENY: privilege escalation, pipe-to-shell
    - Compound commands (&&, ||, ;, |): each segment classified
      independently, strictest verdict wins
    - Unrecognized commands default to REQUIRE_APPROVAL (fail safe)

:func:`classify_file_tool`
    Classifies ``create`` / ``edit`` / ``insert`` calls using
    structured arguments.  **Sandbox-aware and path-aware**:

    ==================  ==========  ================
    Path                Quicksand    NullSandbox
    ==================  ==========  ================
    ``/workspace/…``    ALLOW       REQUIRE_APPROVAL
    ``/mounts/…``       REQ_APPR    REQUIRE_APPROVAL
    Other               REQ_APPR    REQUIRE_APPROVAL
    ==================  ==========  ================

For the full approval matrix (including approval policy, general tools,
and how these classifiers fit together), see the docstring of
``_omni_agent._check_tool_approval()``.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class CommandVerdict(str, Enum):
    """Result of classifying a bash command."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class ApprovalCategory(str, Enum):
    """Why the command needs approval (or was denied)."""

    DESTRUCTIVE_FILE_OP = "destructive_file_op"
    NETWORK_ACCESS = "network_access"
    CODE_EXECUTION = "code_execution"
    SYSTEM_MODIFICATION = "system_modification"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PACKAGE_MANAGEMENT = "package_management"
    PROCESS_MANAGEMENT = "process_management"
    DANGEROUS_GIT_OP = "dangerous_git_op"


class ClassificationResult(NamedTuple):
    """Return value of :func:`classify_bash_command`."""

    verdict: CommandVerdict
    category: ApprovalCategory | None
    reason: str


#: Unified callback signature for ``Tool.approval_check``.
#: Called as ``check(tool_name, tool_args, is_sandbox)``.
ApprovalCheck = Callable[[str, dict[str, Any], bool], ClassificationResult]


# ---------------------------------------------------------------------------
# ALLOW list — read-only, no-side-effect commands
# ---------------------------------------------------------------------------

_ALLOW_COMMANDS: frozenset[str] = frozenset(
    {
        # File/directory listing & inspection
        "ls",
        "dir",
        "stat",
        "file",
        "du",
        "df",
        "lsblk",
        "tree",
        "realpath",
        "readlink",
        "basename",
        "dirname",
        # File content viewing
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "nl",
        "tac",
        "rev",
        "strings",
        "xxd",
        "hexdump",
        "od",
        # Text processing (read-only)
        "grep",
        "egrep",
        "fgrep",
        "awk",
        "sed",  # sed without -i is read-only; sed -i is caught by _REQUIRE_APPROVAL_PATTERNS (checked first)
        "cut",
        "sort",  # sort without -o is read-only; sort -o is caught by _UNSAFE_FLAGS
        "uniq",
        "tr",
        "wc",
        "diff",
        "comm",
        "paste",
        "column",
        "fold",
        "fmt",
        "expand",
        "unexpand",
        "jq",
        # Search
        "find",  # find without -delete/-exec rm is read-only
        "which",
        "whereis",
        "locate",
        "type",
        # Information
        "pwd",
        "whoami",
        "id",
        "hostname",
        "uname",
        "date",
        "cal",
        "uptime",
        "env",
        "printenv",
        "echo",
        "printf",
        "true",
        "false",
        "test",
        "[",
        # Archive inspection (read-only, but only listing modes)
        "zipinfo",
        # Git read-only
        "git",  # git without push/reset/clean is read-only; handled specially
        # Encoding (safe without output flags; flag check handles -o)
        "base64",
        # Search tools (safe without external-command flags; flag check handles --pre etc.)
        "rg",
        "ripgrep",
        # Misc read-only
        "md5sum",
        "sha256sum",
        "sha1sum",
        "b2sum",
        "cksum",
        "sum",
        "seq",
        "expr",
        "bc",
        "dc",
        "man",
        "help",
        "info",
    }
)

# ---------------------------------------------------------------------------
# DENY patterns — always blocked
# ---------------------------------------------------------------------------

_DENY_PATTERNS: list[tuple[re.Pattern[str], ApprovalCategory, str]] = [
    # Privilege escalation
    (
        re.compile(r"(?:^|\s)sudo(?:\s|$)"),
        ApprovalCategory.PRIVILEGE_ESCALATION,
        "This command uses sudo for privilege escalation.",
    ),
    (
        re.compile(r"(?:^|\s)su(?:\s|$)"),
        ApprovalCategory.PRIVILEGE_ESCALATION,
        "This command switches to another user.",
    ),
    (
        re.compile(r"(?:^|\s)doas(?:\s|$)"),
        ApprovalCategory.PRIVILEGE_ESCALATION,
        "This command uses doas for privilege escalation.",
    ),
    # Pipe to shell — remote code execution
    (
        re.compile(r"\|\s*(?:bash|sh|zsh|dash|ksh|csh|tcsh|fish)(?:\s|$)"),
        ApprovalCategory.PRIVILEGE_ESCALATION,
        "This command pipes output to a shell interpreter.",
    ),
    # curl/wget piped to shell
    (
        re.compile(
            r"(?:curl|wget)\s.*\|\s*(?:bash|sh|zsh|dash|ksh|python|perl|ruby|node)"
        ),
        ApprovalCategory.PRIVILEGE_ESCALATION,
        "This command downloads and executes remote code.",
    ),
]

# ---------------------------------------------------------------------------
# REQUIRE_APPROVAL patterns — need user confirmation
# ---------------------------------------------------------------------------

_REQUIRE_APPROVAL_PATTERNS: list[tuple[re.Pattern[str], ApprovalCategory, str]] = [
    # Destructive file operations
    (
        re.compile(r"(?:^|\s)rm\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will delete files from your system.",
    ),
    (
        re.compile(r"(?:^|\s)rmdir\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will remove a directory from your system.",
    ),
    (
        re.compile(r"(?:^|\s)shred\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will securely delete files from your system.",
    ),
    (
        re.compile(r"(?:^|\s)mv\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will move or rename files on your system.",
    ),
    (
        re.compile(r"(?:^|\s)cp\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This may overwrite existing files.",
    ),
    (
        re.compile(r"(?:^|\s)truncate\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will resize a file on your system.",
    ),
    (
        re.compile(r"\bfind\b.*\s-delete\b"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will delete multiple files from your system.",
    ),
    (
        re.compile(r"\bfind\b.*-exec\s+rm\b"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will delete multiple files from your system.",
    ),
    # sed -i (in-place editing)
    (
        re.compile(r"(?:^|\s)sed\s.*-i"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will modify a file in place.",
    ),
    # Redirects that create/overwrite files
    (
        re.compile(r">\s*\S"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This may create or overwrite a file.",
    ),
    # Network access
    (
        re.compile(r"(?:^|\s)curl\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will make a network request.",
    ),
    (
        re.compile(r"(?:^|\s)wget\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will download files from the network.",
    ),
    (
        re.compile(r"(?:^|\s)nc\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will open a network connection.",
    ),
    (
        re.compile(r"(?:^|\s)netcat\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will open a network connection.",
    ),
    (
        re.compile(r"(?:^|\s)ssh\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will open a remote shell connection.",
    ),
    (
        re.compile(r"(?:^|\s)scp\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will copy files to/from a remote server.",
    ),
    (
        re.compile(r"(?:^|\s)rsync\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will sync files with a remote server.",
    ),
    (
        re.compile(r"(?:^|\s)ftp\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will transfer files over FTP.",
    ),
    (
        re.compile(r"(?:^|\s)sftp\s"),
        ApprovalCategory.NETWORK_ACCESS,
        "This will transfer files over SFTP.",
    ),
    # Process management (before code-execution patterns so that
    # ``killall python`` is classified as PROCESS_MANAGEMENT, not
    # CODE_EXECUTION)
    (
        re.compile(r"(?:^|\s)kill\s"),
        ApprovalCategory.PROCESS_MANAGEMENT,
        "This will terminate a process.",
    ),
    (
        re.compile(r"(?:^|\s)killall\s"),
        ApprovalCategory.PROCESS_MANAGEMENT,
        "This will terminate processes by name.",
    ),
    (
        re.compile(r"(?:^|\s)pkill\s"),
        ApprovalCategory.PROCESS_MANAGEMENT,
        "This will terminate processes by pattern.",
    ),
    # Code execution
    (
        re.compile(r"(?:^|\s)python[23]?(?:\s|$)"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute code on your system.",
    ),
    (
        re.compile(r"(?:^|\s)node\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute code on your system.",
    ),
    (
        re.compile(r"(?:^|\s)ruby\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute code on your system.",
    ),
    (
        re.compile(r"(?:^|\s)perl\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute code on your system.",
    ),
    (
        re.compile(r"(?:^|\s)bash\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute a script on your system.",
    ),
    (
        re.compile(r"(?:^|\s)sh\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute a script on your system.",
    ),
    (
        re.compile(r"(?:^|\s)zsh\s"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute a script on your system.",
    ),
    (
        re.compile(r"^(?:\w+=\S*\s+)*\./[^\s.]"),
        ApprovalCategory.CODE_EXECUTION,
        "This will execute a local file.",
    ),
    # Package management
    (
        re.compile(r"(?:^|\s)pip3?\s+install\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will install packages on your system.",
    ),
    (
        re.compile(r"(?:^|\s)pip3?\s+uninstall\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will remove packages from your system.",
    ),
    (
        re.compile(r"(?:^|\s)npm\s+install\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will install packages on your system.",
    ),
    (
        re.compile(r"(?:^|\s)apt(?:-get)?\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will modify system packages.",
    ),
    (
        re.compile(r"(?:^|\s)yum\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will modify system packages.",
    ),
    (
        re.compile(r"(?:^|\s)brew\s+install\s"),
        ApprovalCategory.PACKAGE_MANAGEMENT,
        "This will install packages on your system.",
    ),
    # Dangerous git operations
    (
        re.compile(r"(?:^|\s)git\s+push\s.*--force"),
        ApprovalCategory.DANGEROUS_GIT_OP,
        "This will force-push to a remote repository.",
    ),
    (
        re.compile(r"(?:^|\s)git\s+push\s.*-f\b"),
        ApprovalCategory.DANGEROUS_GIT_OP,
        "This will force-push to a remote repository.",
    ),
    (
        re.compile(r"(?:^|\s)git\s+reset\s+--hard"),
        ApprovalCategory.DANGEROUS_GIT_OP,
        "This will discard uncommitted changes.",
    ),
    (
        re.compile(r"(?:^|\s)git\s+clean\s.*-f"),
        ApprovalCategory.DANGEROUS_GIT_OP,
        "This will delete untracked files.",
    ),
    (
        re.compile(r"(?:^|\s)git\s+checkout\s.*--\s"),
        ApprovalCategory.DANGEROUS_GIT_OP,
        "This will discard local changes to files.",
    ),
    # System modification
    (
        re.compile(r"(?:^|\s)chmod\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will change file permissions.",
    ),
    (
        re.compile(r"(?:^|\s)chown\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will change file ownership.",
    ),
    (
        re.compile(r"(?:^|\s)chgrp\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will change the file group.",
    ),
    (
        re.compile(r"(?:^|\s)ln\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will create filesystem links.",
    ),
    (
        re.compile(r"(?:^|\s)mount\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will mount a filesystem.",
    ),
    (
        re.compile(r"(?:^|\s)umount\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will unmount a filesystem.",
    ),
    (
        re.compile(r"(?:^|\s)dd\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will perform a low-level data copy.",
    ),
    (
        re.compile(r"(?:^|\s)mkfs\b"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will create a filesystem.",
    ),
    (
        re.compile(r"(?:^|\s)fdisk\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will modify disk partitions.",
    ),
    (
        re.compile(r"(?:^|\s)crontab\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will modify scheduled tasks.",
    ),
    (
        re.compile(r"(?:^|\s)systemctl\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will manage system services.",
    ),
    (
        re.compile(r"(?:^|\s)service\s"),
        ApprovalCategory.SYSTEM_MODIFICATION,
        "This will manage system services.",
    ),
    # File creation
    (
        re.compile(r"(?:^|\s)mkdir\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will create a new directory.",
    ),
    (
        re.compile(r"(?:^|\s)touch\s"),
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will create or modify a file.",
    ),
    # Unbounded output (DoS risk)
    (
        re.compile(r"(?:^|\s)yes(?:\s|$)"),
        ApprovalCategory.CODE_EXECUTION,
        "This command produces unbounded output.",
    ),
]


# ---------------------------------------------------------------------------
# Git read-only subcommands (when base command is 'git')
# ---------------------------------------------------------------------------

_GIT_READONLY_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status",
        "log",
        "diff",
        "show",
        "branch",
        "tag",
        "describe",
        "rev-parse",
        "rev-list",
        "ls-files",
        "ls-tree",
        "ls-remote",
        "shortlog",
        "blame",
        "bisect",
        "reflog",
        "cat-file",
        "name-rev",
        "cherry",
        "grep",
        "count-objects",
        "fsck",
        "verify-pack",
        "help",
        "version",
    }
)

# Git global options that can redirect config, repository, or helper lookup,
# making otherwise read-only git commands execute attacker-controlled code.
_GIT_UNSAFE_GLOBAL_OPTIONS_WITH_VALUE: frozenset[str] = frozenset(
    {
        "-c",
        "--config-env",
        "--exec-path",
        "--git-dir",
        "--namespace",
        "--super-prefix",
        "--work-tree",
    }
)

# These are the same options but with inline =value syntax
_GIT_UNSAFE_GLOBAL_OPTION_PREFIXES: tuple[str, ...] = (
    "--config-env=",
    "--exec-path=",
    "--git-dir=",
    "--namespace=",
    "--super-prefix=",
    "--work-tree=",
)

# Git subcommand args that can write to disk or execute external tools
_GIT_UNSAFE_SUBCOMMAND_FLAGS: frozenset[str] = frozenset(
    {
        "--output",
        "--ext-diff",
        "--textconv",
        "--exec",
        "--paginate",
    }
)

# ---------------------------------------------------------------------------
# Flag-aware ALLOW list — commands safe only without certain flags
# ---------------------------------------------------------------------------

# Commands that are read-only by default but become unsafe with output flags.
# Map: command -> set of flags that make it unsafe
_UNSAFE_FLAGS: dict[str, list[str]] = {
    "base64": ["-o", "--output"],
    "sort": ["-o", "--output"],
    "tail": ["-f", "-F", "--follow"],
    "rg": [
        "--pre",
        "--pre=",
        "--hostname-bin",
        "--hostname-bin=",
        "--search-zip",
        "-z",
    ],
    "ripgrep": [
        "--pre",
        "--pre=",
        "--hostname-bin",
        "--hostname-bin=",
        "--search-zip",
        "-z",
    ],
    "find": [
        "-delete",
        "-exec",
        "-execdir",
        "-ok",
        "-okdir",
        "-fls",
        "-fprint",
        "-fprint0",
        "-fprintf",
    ],
}


# ---------------------------------------------------------------------------
# Compound command splitting
# ---------------------------------------------------------------------------

# Regex that splits on unquoted shell operators: &&, ||, ;, |
# This is intentionally simple — it won't handle all edge cases
# (e.g. operators inside single quotes) but covers common patterns.
_SHELL_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||[;|])\s*")


def split_compound(command: str) -> list[str]:
    """Split a compound command into individual segments.

    Handles ``&&``, ``||``, ``;``, and ``|`` as delimiters.
    Returns a list of non-empty stripped segments.
    """
    segments = _SHELL_SPLIT_RE.split(command)
    return [s.strip() for s in segments if s.strip()]


def base_command(segment: str) -> str:
    """Extract the base command name from a single command segment.

    Strips leading environment variable assignments (``FOO=bar cmd ...``)
    and returns the first real token.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        # Malformed quoting — fall back to simple split
        tokens = segment.split()

    for token in tokens:
        # Skip env var assignments (KEY=VALUE)
        if "=" in token and not token.startswith("-"):
            parts = token.split("=", 1)
            # Must look like a valid env var name
            if parts[0].replace("_", "").isalnum():
                continue
        return token

    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_bash_command(
    command: str, is_sandbox: bool = True
) -> ClassificationResult:
    """Classify a bash command string.

    Args:
        command: The full bash command string (may be compound).
        is_sandbox: True if running inside a real sandbox (Quicksand,
            Bubblewrap). When False (NullSandbox), additional checks
            fire: read commands targeting paths in the denylist
            (``~/.ssh``, ``/etc/shadow``, …) require approval, since
            the agent shares the host filesystem.

    Returns:
        A ``ClassificationResult`` with the verdict, optional category,
        and human-readable reason.
    """
    command = command.strip()
    if not command:
        return ClassificationResult(CommandVerdict.ALLOW, None, "Empty command")

    # Check DENY patterns on the FULL command first (catches cross-segment
    # patterns like "curl ... | bash" before splitting on |)
    for pattern, category, reason in _DENY_PATTERNS:
        if pattern.search(command):
            return ClassificationResult(CommandVerdict.DENY, category, reason)

    segments = split_compound(command)

    # Classify each segment independently; keep the strictest result
    worst = ClassificationResult(CommandVerdict.ALLOW, None, "Safe command")

    for segment in segments:
        result = _classify_single(segment)
        if _severity(result.verdict) > _severity(worst.verdict):
            worst = result

    # Under NullSandbox, also gate any reference to sensitive host paths.
    # In a real sandbox those paths aren't reachable, so this check is
    # redundant; under NullSandbox it's the only line of defense.
    if not is_sandbox and _severity(worst.verdict) < _severity(
        CommandVerdict.REQUIRE_APPROVAL
    ):
        from ...sandbox._path_validator import find_denied_path_in_command

        matched = find_denied_path_in_command(command)
        if matched is not None:
            worst = ClassificationResult(
                CommandVerdict.REQUIRE_APPROVAL,
                ApprovalCategory.DESTRUCTIVE_FILE_OP,
                f"This command references a sensitive host path ({matched}).",
            )

    return worst


def classify_sensitive_read(path: str, is_sandbox: bool) -> ClassificationResult:
    """Classify a read tool's path argument (e.g. for ``open``).

    Inside a real sandbox the host's sensitive paths aren't reachable,
    so reads are always allowed. Under NullSandbox, paths in the
    denylist (``~/.ssh``, ``/etc/shadow``, …) require approval.
    """
    if is_sandbox:
        return ClassificationResult(CommandVerdict.ALLOW, None, "")

    from ...sandbox._path_normalizer import get_home
    from ...sandbox._path_validator import expand_tilde_and_home, is_denied_path

    # Expand ``~`` against get_home(); the denylist anchors to both
    # get_home() and get_runtime_home(), so the credential dir is flagged
    # whichever home the shell would actually resolve ``~`` to on WSL.
    expanded = expand_tilde_and_home(path, str(get_home()))
    denied, matched = is_denied_path(Path(expanded).resolve())
    if denied:
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL,
            ApprovalCategory.DESTRUCTIVE_FILE_OP,
            f"This will read a sensitive host path ({matched}).",
        )
    return ClassificationResult(CommandVerdict.ALLOW, None, "")


def _severity(verdict: CommandVerdict) -> int:
    """Numeric severity for comparison (higher = stricter)."""
    return {
        CommandVerdict.ALLOW: 0,
        CommandVerdict.REQUIRE_APPROVAL: 1,
        CommandVerdict.DENY: 2,
    }[verdict]


def _classify_single(segment: str) -> ClassificationResult:
    """Classify a single (non-compound) command segment."""

    # 1. Check DENY patterns first (full segment, catches pipes etc.)
    for pattern, category, reason in _DENY_PATTERNS:
        if pattern.search(segment):
            return ClassificationResult(CommandVerdict.DENY, category, reason)

    # 2. Check REQUIRE_APPROVAL patterns
    for pattern, category, reason in _REQUIRE_APPROVAL_PATTERNS:
        if pattern.search(segment):
            return ClassificationResult(
                CommandVerdict.REQUIRE_APPROVAL, category, reason
            )

    # 3. Check ALLOW list by base command
    base = base_command(segment)
    if not base:
        return ClassificationResult(CommandVerdict.ALLOW, None, "Empty segment")

    # Special handling for git
    if base == "git":
        return _classify_git(segment)

    # Special handling for tar/unzip: only listing modes are safe
    if base in ("tar", "unzip"):
        return _classify_archive(base, segment)

    if base in _ALLOW_COMMANDS:
        # 4. Flag-aware check: some ALLOW commands become unsafe with certain flags
        unsafe_flags = _UNSAFE_FLAGS.get(base)
        if unsafe_flags:
            try:
                tokens = shlex.split(segment)
            except ValueError:
                tokens = segment.split()
            for token in tokens[1:]:
                for flag in unsafe_flags:
                    if flag.endswith("="):
                        # Prefix match for --flag=value syntax
                        if token.startswith(flag):
                            return ClassificationResult(
                                CommandVerdict.REQUIRE_APPROVAL,
                                ApprovalCategory.DESTRUCTIVE_FILE_OP,
                                f"This command uses an unsafe flag ({flag.rstrip('=')}).",
                            )
                    elif token == flag:
                        return ClassificationResult(
                            CommandVerdict.REQUIRE_APPROVAL,
                            ApprovalCategory.DESTRUCTIVE_FILE_OP,
                            f"This command uses an unsafe flag ({flag}).",
                        )

        return ClassificationResult(CommandVerdict.ALLOW, None, f"Safe command: {base}")

    # 5. Default: require approval (fail safe)
    return ClassificationResult(
        CommandVerdict.REQUIRE_APPROVAL,
        ApprovalCategory.CODE_EXECUTION,
        "This command is not recognized as safe.",
    )


def _classify_git(segment: str) -> ClassificationResult:
    """Classify a git command based on subcommand and global options."""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()

    # Check for unsafe global options first (before even looking at subcommand).
    # These can make otherwise read-only git commands execute arbitrary code.
    for token in tokens[1:]:
        if token in _GIT_UNSAFE_GLOBAL_OPTIONS_WITH_VALUE:
            return ClassificationResult(
                CommandVerdict.REQUIRE_APPROVAL,
                ApprovalCategory.DANGEROUS_GIT_OP,
                f"This git command uses an unsafe global option ({token}).",
            )
        if any(
            token.startswith(prefix) for prefix in _GIT_UNSAFE_GLOBAL_OPTION_PREFIXES
        ):
            return ClassificationResult(
                CommandVerdict.REQUIRE_APPROVAL,
                ApprovalCategory.DANGEROUS_GIT_OP,
                f"This git command uses an unsafe global option ({token.split('=')[0]}).",
            )

    # Find the subcommand (skip flags like --no-pager, -C <path>)
    subcommand = None
    subcommand_idx = 0
    skip_next = False
    for i, token in enumerate(tokens[1:], start=1):
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            # Some flags consume the next token as value
            if token in ("-C",):
                skip_next = True
            continue
        subcommand = token
        subcommand_idx = i
        break

    if subcommand is None:
        return ClassificationResult(CommandVerdict.ALLOW, None, "git: no subcommand")

    if subcommand in _GIT_READONLY_SUBCOMMANDS:
        # Check subcommand args for unsafe flags (--output, --exec, etc.)
        subcommand_args = tokens[subcommand_idx + 1 :]
        for arg in subcommand_args:
            if arg in _GIT_UNSAFE_SUBCOMMAND_FLAGS:
                return ClassificationResult(
                    CommandVerdict.REQUIRE_APPROVAL,
                    ApprovalCategory.DANGEROUS_GIT_OP,
                    f"This git command uses an unsafe flag ({arg}).",
                )
            if any(arg.startswith(f"{f}=") for f in _GIT_UNSAFE_SUBCOMMAND_FLAGS):
                return ClassificationResult(
                    CommandVerdict.REQUIRE_APPROVAL,
                    ApprovalCategory.DANGEROUS_GIT_OP,
                    f"This git command uses an unsafe flag ({arg.split('=')[0]}).",
                )

        # Special handling for `git branch` — only read-only without mutation flags
        if subcommand == "branch":
            if not _git_branch_is_read_only(subcommand_args):
                return ClassificationResult(
                    CommandVerdict.REQUIRE_APPROVAL,
                    ApprovalCategory.DANGEROUS_GIT_OP,
                    "This git branch command may create, rename, or delete branches.",
                )

        return ClassificationResult(
            CommandVerdict.ALLOW, None, f"git {subcommand}: read-only"
        )

    # git add, commit, push (without --force), pull, fetch, merge, rebase, etc.
    return ClassificationResult(
        CommandVerdict.REQUIRE_APPROVAL,
        ApprovalCategory.DANGEROUS_GIT_OP,
        f"This is a git {subcommand} operation that modifies your repository.",
    )


def _git_branch_is_read_only(args: list[str]) -> bool:
    """Check if git branch args indicate a read-only operation.

    ``git branch`` with no args or only listing flags (``-a``, ``-r``, ``-v``,
    ``--list``, ``--format=...``) is read-only. Any other flag or positional
    argument may create, rename, or delete branches.
    """
    if not args:
        return True

    _BRANCH_READ_ONLY_FLAGS = frozenset(
        {
            "-a",
            "--all",
            "-r",
            "--remotes",
            "-v",
            "-vv",
            "--verbose",
            "--list",
            "--show-current",
            "--no-color",
            "--color",
            "--sort",
            "--contains",
            "--merged",
            "--no-merged",
        }
    )

    saw_read_only = False
    for arg in args:
        if arg in _BRANCH_READ_ONLY_FLAGS:
            saw_read_only = True
        elif arg.startswith("--format=") or arg.startswith("--sort="):
            saw_read_only = True
        elif arg.startswith("-"):
            # Unknown flag — might be mutation (e.g. -d, -D, -m, -M, -c, -C)
            return False
        else:
            # Positional argument — branch name for creation
            return False

    return saw_read_only


# ---------------------------------------------------------------------------
# Archive command classification (tar/unzip)
# ---------------------------------------------------------------------------

# tar modes that extract or create (unsafe). Matches both -x and x (no dash).
_TAR_UNSAFE_MODES = frozenset("xc")
_TAR_UNSAFE_LONG = frozenset({"--extract", "--get", "--create"})


def _classify_archive(base: str, segment: str) -> ClassificationResult:
    """Classify tar/unzip — only listing modes are safe."""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()

    if base == "tar":
        for token in tokens[1:]:
            # Long options — check exact unsafe long options only
            if token in _TAR_UNSAFE_LONG:
                return ClassificationResult(
                    CommandVerdict.REQUIRE_APPROVAL,
                    ApprovalCategory.DESTRUCTIVE_FILE_OP,
                    "This will extract or create archive files.",
                )
            # Skip other long options (e.g. --exclude, --xz)
            if token.startswith("--"):
                continue
            # Short options: -xvf, -c, etc.
            if token.startswith("-") and len(token) > 1:
                flags = token[1:]
            elif not token.startswith("/") and "." not in token:
                # Bare flags like xvf (no dash, not a path/file)
                flags = token
            else:
                continue
            if _TAR_UNSAFE_MODES & set(flags):
                return ClassificationResult(
                    CommandVerdict.REQUIRE_APPROVAL,
                    ApprovalCategory.DESTRUCTIVE_FILE_OP,
                    "This will extract or create archive files.",
                )
        # No extract/create mode → listing (tar tf, tar --list)
        return ClassificationResult(
            CommandVerdict.ALLOW, None, "tar: listing mode (safe)"
        )

    # unzip: safe only with explicit -l flag token
    if base == "unzip":
        for token in tokens[1:]:
            if token == "-l" or token == "--list":
                return ClassificationResult(
                    CommandVerdict.ALLOW, None, "unzip -l: listing mode (safe)"
                )
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL,
            ApprovalCategory.DESTRUCTIVE_FILE_OP,
            "This will extract files from an archive.",
        )

    return ClassificationResult(
        CommandVerdict.REQUIRE_APPROVAL,
        ApprovalCategory.CODE_EXECUTION,
        "This command is not recognized as safe.",
    )


# ---------------------------------------------------------------------------
# Path-aware approval for file tools (create/edit/insert)
# ---------------------------------------------------------------------------

_MOUNTS_PATH_SEGMENT = "/mounts/"

# Matches only Quicksand workspace roots at the start of a path:
#   - /workspace/...
#   - /sessions/<id>/workspace/...
# Rejects paths like /tmp/workspace/file.py and /tmp/workspace_evil/.
_WORKSPACE_PATH_RE = re.compile(
    r"^(?:/workspace(?:/|$)|/sessions/[^/]+/workspace(?:/|$))"
)

# Matches actual mount roots — not a workspace sub-directory named "mounts".
#   - /mounts/...
#   - /sessions/<id>/mounts/...
_MOUNTS_PATH_RE = re.compile(r"^(?:/mounts(?:/|$)|/sessions/[^/]+/mounts(?:/|$))")


def is_mount_path(path: str) -> bool:
    """Return True if ``path`` is under a mounts root.

    Recognizes ``/mounts/...`` and ``/sessions/<id>/mounts/...``. A directory
    named ``mounts`` *inside* the workspace (e.g. ``/workspace/mounts/x``)
    does not match.
    """
    return bool(_MOUNTS_PATH_RE.search(path))


def classify_file_tool(
    tool_name: str,
    file_path: str,
    is_sandbox: bool,
) -> ClassificationResult:
    """Classify a file tool operation based on target path and sandbox mode.

    Args:
        tool_name: The tool name (``create``, ``edit``, ``insert``).
        file_path: The guest-side file path (may be relative or absolute).
        is_sandbox: Whether running in a real sandbox (Quicksand).

    Returns:
        A ``ClassificationResult``.
    """
    if not is_sandbox:
        # NullSandbox: all file writes need approval
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL,
            ApprovalCategory.DESTRUCTIVE_FILE_OP,
            "This will write to files on your system (no sandbox).",
        )

    # Tilde-prefixed paths expand to ``$HOME`` in the shell, which sits
    # outside the agent workspace. ``posixpath`` treats ``~`` as a literal
    # path component, so without this early check ``~/foo`` would be
    # classified relative to ``/workspace`` and string-match as safe — but
    # the executor's shell would then write the file under ``$HOME``.
    if file_path.startswith("~"):
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL,
            ApprovalCategory.DESTRUCTIVE_FILE_OP,
            "This will write outside the agent workspace (tilde expands to $HOME).",
        )

    # In sandbox: only workspace writes are safe.
    # The path must contain "/workspace/" as a distinct path segment
    # (e.g. /sessions/<id>/workspace/file.py), not as a substring
    # inside another directory name (e.g. /tmp/workspace_evil/file.py).

    # Resolve the path against the current guest_workspace, then normalize
    # ``..`` segments. File-tool commands execute with cwd=guest_workspace,
    # whose concrete mount path may vary (for example /workspace or
    # /sessions/<id>/workspace). For classification, normalize relative
    # paths to the canonical "/workspace" root used by this policy.
    # Normalizing absolute paths too closes a bypass where a path like
    # ``/workspace/../etc/passwd`` prefix-matches the workspace regex but
    # the kernel resolves ``..`` to ``/etc/passwd`` at write time.
    if posixpath.isabs(file_path):
        resolved = posixpath.normpath(file_path)
    else:
        resolved = posixpath.normpath(posixpath.join("/workspace", file_path))

    # Check workspace *first* so that a directory named "mounts" inside
    # the workspace (e.g. /workspace/mounts/readme.md) is correctly
    # treated as safe rather than flagged by the mount check below.
    if _WORKSPACE_PATH_RE.search(resolved):
        return ClassificationResult(
            CommandVerdict.ALLOW,
            None,
            f"{tool_name}: writing to workspace (safe)",
        )

    if _MOUNTS_PATH_RE.search(resolved):
        # Actual mount root — always require approval
        return ClassificationResult(
            CommandVerdict.REQUIRE_APPROVAL,
            ApprovalCategory.DESTRUCTIVE_FILE_OP,
            "This will write to files outside the agent workspace.",
        )

    # Not in workspace — likely user-mounted directory or unknown path
    return ClassificationResult(
        CommandVerdict.REQUIRE_APPROVAL,
        ApprovalCategory.DESTRUCTIVE_FILE_OP,
        "This will write to files outside the agent workspace.",
    )
