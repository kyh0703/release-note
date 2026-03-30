from __future__ import annotations

import argparse
import json
import sys

from .config import (
    DEFAULT_FILESERVER_URL_TEMPLATE,
    DEFAULT_MAIL_FROM,
    DEFAULT_SMTP_HOST,
    DEFAULT_WIKI_PAGE_TITLE_TEMPLATE,
    RunnerConfig,
)
from .errors import ReleaseNoteError
from .models import ExecutionMode, RunStep, RunSummary
from .runner import ReleaseRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release_note",
        description="Jira/Confluence release-note workflow runner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="preview or apply a single tagging-version workflow",
    )
    run_parser.add_argument(
        "--tagging-version",
        required=True,
        help="release version string such as 6.2.0-b4h19",
    )
    run_parser.add_argument(
        "--username",
        default="",
        help="shared Jira/Confluence username",
    )
    run_parser.add_argument(
        "--password",
        default="",
        help="shared Jira/Confluence password",
    )
    run_parser.add_argument(
        "--fileserver-url-template",
        default=DEFAULT_FILESERVER_URL_TEMPLATE,
        help="fileserver URL template",
    )
    run_parser.add_argument(
        "--wiki-page-title-template",
        default=DEFAULT_WIKI_PAGE_TITLE_TEMPLATE,
        help="Confluence target page title template",
    )
    run_parser.add_argument(
        "--notify-open-issues",
        action="store_true",
        help="send notification emails for non-closed Jira issues grouped by assignee",
    )
    run_parser.add_argument(
        "--smtp-host",
        default=DEFAULT_SMTP_HOST,
        help="SMTP host for open issue notifications",
    )
    run_parser.add_argument(
        "--smtp-port",
        type=int,
        help="SMTP port override",
    )
    run_parser.add_argument(
        "--smtp-use-tls",
        action="store_true",
        help="enable STARTTLS for SMTP notifications",
    )
    run_parser.add_argument(
        "--smtp-use-ssl",
        action="store_true",
        help="use SMTPS for SMTP notifications",
    )
    run_parser.add_argument(
        "--smtp-username",
        default="",
        help="SMTP username for open issue notifications",
    )
    run_parser.add_argument(
        "--smtp-password",
        default="",
        help="SMTP password for open issue notifications",
    )
    run_parser.add_argument(
        "--mail-from",
        default=DEFAULT_MAIL_FROM,
        help="From address for open issue notifications",
    )
    run_parser.add_argument(
        "--mail-reply-to",
        default="",
        help="Reply-To address for open issue notifications",
    )
    mode = run_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="preview planned changes")
    mode.add_argument("--apply", action="store_true", help="perform write operations")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            config = RunnerConfig.from_cli_options(
                username=args.username,
                password=args.password,
                fileserver_url_template=args.fileserver_url_template,
                wiki_page_title_template=args.wiki_page_title_template,
                notify_open_issues=args.notify_open_issues,
                smtp_host=args.smtp_host,
                smtp_port=args.smtp_port,
                smtp_use_tls=args.smtp_use_tls,
                smtp_use_ssl=args.smtp_use_ssl,
                smtp_username=args.smtp_username,
                smtp_password=args.smtp_password,
                mail_from=args.mail_from,
                mail_reply_to=args.mail_reply_to,
            )
            mode = ExecutionMode.APPLY if args.apply else ExecutionMode.DRY_RUN
            summary = ReleaseRunner(
                config,
                step_reporter=_emit_step,
                run_start_reporter=_emit_run_start,
            ).run(args.tagging_version, mode)
            print("summary:", flush=True)
            print(summary.to_text())
            return 0
        parser.error(f"Unsupported command: {args.command}")
    except ReleaseNoteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _emit_run_start(summary: RunSummary) -> None:
    print("run started", flush=True)
    print(f"mode: {summary.execution_mode.value}", flush=True)
    print(f"tagging_version: {summary.tagging_version}", flush=True)
    print(f"target_page_title: {summary.target_page_title}", flush=True)
    print(f"next_patch_version: {summary.next_patch_version}", flush=True)
    print(f"release_date: {summary.release_date}", flush=True)
    if summary.fileserver_url is not None:
        print(f"fileserver_url: {summary.fileserver_url}", flush=True)


def _emit_step(step: RunStep) -> None:
    print(f"step [{step.status}] {step.name}: {step.message}", flush=True)
    if step.payload:
        print(
            f"step payload: {json.dumps(step.payload, ensure_ascii=False, sort_keys=True)}",
            flush=True,
        )
