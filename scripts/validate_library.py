#!/usr/bin/env python3
"""Check the template library. Read-only. Does not print secret values."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reference.reply_gate import decide  # noqa: E402
from reference.schema_check import validate as check_schema  # noqa: E402

REQUIRED_SECTIONS = (
    "## Mission",
    "## Scope",
    "## Required context",
    "## Intake and triage",
    "## Workflow",
    "## Drafting rules",
    "## Escalation",
    "## Reply policy",
    "## Rubric",
    "## Done criteria",
)

EXAMPLE_SCHEMA_PAIRS = (
    ("examples/events/handled-record.json", "shared/schemas/handled-record.schema.json"),
    ("examples/events/attempt-record.json", "shared/schemas/attempt-record.schema.json"),
    ("examples/events/inbound-event.json", "shared/schemas/inbound-event.schema.json"),
    ("examples/events/triage-report.json", "shared/schemas/triage-report.schema.json"),
    ("examples/events/draft-record.json", "shared/schemas/draft-record.schema.json"),
    ("examples/events/approval-record.json", "shared/schemas/approval-record.schema.json"),
    ("examples/events/ses-receipt-notification.json", "shared/schemas/ses-receipt-notification.schema.json"),
)

ALLOWED_EMAIL_SUFFIXES = (
    "example.com",
    "example.net",
    "example.org",
    "amazonses.com",
    "amazonaws.com",
)
ALLOWED_URL_HOSTS = (
    "docs.aws.amazon.com",
    "docs.cloudflare.com",
    "developers.cloudflare.com",
    "example.com",
    "www.example.com",
)

SECRET_RULES = (
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_temp_key_id", re.compile(r"ASIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("slack_webhook", re.compile(r"hooks\.slack\.com")),
    ("stripe_live", re.compile(r"sk_live_[0-9A-Za-z]+")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("arn_account_id", re.compile(r"arn:aws:[^:\s]+:[^:\s]*:[0-9]{12}:")),
)
DENY_TOKENS = ("".join(("we", "ave")),)
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@((?:[\w-]+\.)+[A-Za-z]{2,})")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def main():
    errors = validate()
    if errors:
        print(f"{len(errors)} library check(s) failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("library checks passed")
    return 0


def validate():
    errors = []
    errors.extend(_skills())
    errors.extend(_policies())
    errors.extend(_config())
    errors.extend(_examples())
    errors.extend(_links_and_secrets())
    errors.extend(_readme())
    return errors


def _skills():
    errors = []
    roles = json.loads((ROOT / "catalog" / "roles.json").read_text(encoding="utf-8"))
    if len(roles) < 30:
        errors.append(f"catalog has {len(roles)} roles; expected at least 30")
    slugs = [role["slug"] for role in roles]
    if len(slugs) != len(set(slugs)):
        errors.append("duplicate role slug in catalog")
    directories = sorted(path.parent.name for path in (ROOT / "Job").glob("*/SKILL.md"))
    if directories != sorted(slugs):
        errors.append("Job directories and catalog slugs differ")
    index = (ROOT / "catalog" / "INDEX.md").read_text(encoding="utf-8")
    for role in roles:
        skill = ROOT / role["skill"]
        if not skill.is_file():
            errors.append(f"missing skill {role['skill']}")
            continue
        text = skill.read_text(encoding="utf-8")
        front = _frontmatter(text)
        if front.get("name") != role["slug"]:
            errors.append(f"{role['skill']} frontmatter name mismatch")
        if not front.get("description"):
            errors.append(f"{role['skill']} missing description")
        for section in REQUIRED_SECTIONS:
            if section not in text:
                errors.append(f"{role['skill']} missing {section}")
        if f"../{role['skill']}" not in index and f"](../{role['skill']})" not in index:
            errors.append(f"catalog index missing link to {role['skill']}")
        if role["default_auto_send"] is not False:
            errors.append(f"{role['slug']} default_auto_send must be false")
    core = (ROOT / "shared" / "core" / "SKILL.md").read_text(encoding="utf-8")
    if _frontmatter(core).get("name") != "inbox-core":
        errors.append("core skill name must be inbox-core")
    for section in REQUIRED_SECTIONS:
        if section not in core:
            errors.append(f"core skill missing {section}")
    return errors


def _policies():
    errors = []
    roles = json.loads((ROOT / "catalog" / "roles.json").read_text(encoding="utf-8"))
    slugs = [role["slug"] for role in roles]
    default = _load("shared/policies/auto-reply-authorization.example.json")
    hello = _load("shared/policies/hello-first-reply.example.json")
    if default["kill_switch"]["global"] is not True:
        errors.append("default policy kill switch must be on")
    if default["auto_reply"]["human_only_roles"] != slugs:
        errors.append("default policy human_only_roles must match the catalog")
    if default["auto_reply"]["rules"] != []:
        errors.append("default policy must not ship send rules")
    if hello["kill_switch"]["global"] is not True:
        errors.append("hello example kill switch must be on")
    hello_only = hello["auto_reply"]["human_only_roles"]
    if "hello" in hello_only:
        errors.append("hello example must leave hello out of human_only so the shape can be tested")
    for slug in ("sales", "support", "projects"):
        if slug not in hello_only:
            errors.append(f"hello example must keep {slug} human-only")
    if sorted(hello_only) != sorted(slug for slug in slugs if slug != "hello"):
        errors.append("hello example human_only set must be every role except hello")
    rules = hello["auto_reply"]["rules"]
    if len(rules) != 1 or rules[0]["enabled"] is not False:
        errors.append("hello example rule must be present and disabled")
    rule = rules[0]
    if rule["role"] != "hello" or rule["intent"] != "first_reply_new_inquiry":
        errors.append("hello example rule must be the first-reply intent")
    if rule["mode"] != "template_only" or rule["deny_if_follow_up"] is not True:
        errors.append("hello example rule must be template-only and deny follow-ups")
    if set(rule["allow_audiences"]) != {"new_inquiry", "routing"}:
        errors.append("hello example audiences must be new_inquiry and routing")
    decision = decide(_perfect_hello_request(), default, _rates())
    if decision["action"] != "do_not_send" or decision["reasons"] != ["kill_switch_global"]:
        errors.append(f"default policy must stop a perfect hello request on the kill switch, got {decision}")
    return errors


def _config():
    errors = []
    config = _load("shared/config/acme.example.json")
    ids = [item["id"] for item in config["wake"]["alternatives"]]
    if ids != ["sns_worker_queue", "coordinator_fanout", "peer_wake"]:
        errors.append("reference config must list the three wake alternatives")
    if config["approval"]["rubric_grants_send_authority"] is not False:
        errors.append("config must say the rubric does not grant send authority")
    if config["runtime"]["polling"]["default"] != "disabled":
        errors.append("polling must default to disabled")
    observed = _load("shared/config/observed-multi-role.example.json")
    if observed["authorization"]["sales"] != "human_approval_every_external_send":
        errors.append("observed profile must keep sales on human approval")
    if "sender" in observed.get("common", {}):
        errors.append("observed profile must not claim a separate sender was verified for every role")
    return errors


def _examples():
    errors = []
    for example, schema in EXAMPLE_SCHEMA_PAIRS:
        instance = _load(example)
        schema_data = _load(schema)
        for problem in check_schema(instance, schema_data):
            errors.append(f"{example}: {problem}")
    for path in (ROOT / "shared" / "templates").glob("*"):
        if path.suffix not in {".txt", ".html"}:
            continue
        if "cid:" in path.read_text(encoding="utf-8").lower():
            errors.append(f"{path.relative_to(ROOT)} contains a cid reference")
    return errors


def _links_and_secrets():
    errors = []
    for path in _text_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        for name, pattern in SECRET_RULES:
            if pattern.search(text):
                errors.append(f"{relative} matched {name}")
        lowered = text.lower()
        for token in DENY_TOKENS:
            if token in lowered:
                errors.append(f"{relative} matched a denylisted token")
        for match in EMAIL_RE.finditer(text):
            domain = match.group(1).lower()
            if not any(domain == suffix or domain.endswith("." + suffix) for suffix in ALLOWED_EMAIL_SUFFIXES):
                errors.append(f"{relative} has an email outside the example domains")
                break
        if path.suffix.lower() != ".md":
            continue
        visible = FENCE_RE.sub("", text)
        for raw in LINK_RE.findall(visible):
            target = raw.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                if target.startswith(("http://", "https://")):
                    host = target.split("/", 3)[2].lower()
                    if host not in ALLOWED_URL_HOSTS:
                        errors.append(f"{relative} links to unapproved host {host}")
                continue
            destination = (path.parent / target).resolve()
            try:
                destination.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{relative} links outside the repo: {target}")
                continue
            if not destination.exists():
                errors.append(f"{relative} broken link {target}")
    return errors


def _readme():
    errors = []
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "Lessons from a multi-role deployment",
        "append-only",
        "read-only",
        "In-Reply-To",
        "kill switch",
        "human approval",
        "first reply",
    )
    for phrase in required:
        if phrase not in text:
            errors.append(f"README missing {phrase}")
    if "Cloudflare receives SES" in text or "Cloudflare receives Amazon SES" in text:
        errors.append("README claims Cloudflare receives SES mail")
    return errors


def _perfect_hello_request():
    return {
        "role": "hello",
        "intent": "first_reply_new_inquiry",
        "audience": "new_inquiry",
        "prohibited_categories": [],
        "rubric_pass": True,
        "confidence": 0.99,
        "template_id": "hello-first-inquiry",
        "sender_is_mailing_list": False,
        "sender_is_noreply": False,
        "reply_recipient_count": 1,
        "dmarc_pass": True,
        "header_from": ["pat@example.net"],
        "envelope_mail_from": "bounce@example.net",
        "reply_to": [],
        "auto_reply_destination": "pat@example.net",
        "has_attachment": False,
        "freeform_body": False,
        "is_follow_up": False,
        "thread_already_replied": False,
        "is_test_or_notice": False,
        "suppression_or_opt_out": False,
        "already_sent": False,
        "already_pending_send": False,
        "virus_verdict_fail": False,
        "spam_verdict_fail": False,
    }


def _rates():
    return {"role_sent_last_hour": 0, "sender_sent_last_day": 0, "recipient_sent_last_hour": 0}


def _frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def _load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _text_files():
    skipped = {".git", ".venv", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skipped for part in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".json", ".py", ".yml", ".yaml", ".txt", ".html", ".eml"}:
            continue
        yield path


if __name__ == "__main__":
    sys.exit(main())
