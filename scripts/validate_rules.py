#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则库结构校验。

用途：在 CI 与本地提交前跑一遍，保证 rules/v0.1.yaml 的结构完整性。
它不判断法条内容是否正确（那需要人工核对），只保证"引用可解析、字段不缺失、
ID 不重复"，从而让下游的引用校验有一个可靠的地基。

退出码：0 通过 / 1 有错误
"""

import io
import re
import sys
from datetime import date

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

RULE_FILE = "rules/v0.1.yaml"

REQUIRED_FIELDS = [
    "id", "title", "domain", "roles", "risk",
    "trigger", "question", "pass_criteria", "evidence_required",
    "legal_basis",
]
BASIS_FIELDS = ["law", "article", "quote_type", "quote", "effective_from"]
VALID_ROLES = {"A", "B", "C", "D"}
VALID_RISK = {"high", "medium", "low"}
VALID_QUOTE_TYPE = {"原文", "概括"}
ID_PATTERN = re.compile(r"^GEN-\d{2,}$")

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load():
    try:
        with io.open(RULE_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("ERROR: %s not found (run from repo root)" % RULE_FILE)
        sys.exit(1)
    except yaml.YAMLError as e:
        print("ERROR: YAML parse failed\n%s" % e)
        sys.exit(1)


def main():
    data = load()
    if not isinstance(data, dict) or "rules" not in data:
        print("ERROR: top-level 'rules' key missing")
        sys.exit(1)

    rules = data["rules"]
    meta = data.get("meta", {})

    # --- meta ---
    declared = meta.get("item_count")
    if declared != len(rules):
        err("meta.item_count=%s 与实际条目数 %d 不一致" % (declared, len(rules)))

    domains = set(meta.get("domains", []))

    # --- 逐条 ---
    seen_ids = {}
    for i, r in enumerate(rules):
        loc = "rules[%d]" % i
        if not isinstance(r, dict):
            err("%s 不是 mapping" % loc)
            continue

        rid = r.get("id", "?")
        loc = "%s (%s)" % (loc, rid)

        for f in REQUIRED_FIELDS:
            if f not in r or r[f] in (None, "", []):
                err("%s 缺少字段 %s" % (loc, f))

        if rid in seen_ids:
            err("ID 重复: %s (第 %d 与第 %d 条)" % (rid, seen_ids[rid], i))
        else:
            seen_ids[rid] = i

        if not ID_PATTERN.match(str(rid)):
            err("%s ID 格式应为 GEN-两位数字" % loc)

        roles = r.get("roles") or []
        bad = set(roles) - VALID_ROLES
        if bad:
            err("%s roles 含非法值 %s" % (loc, sorted(bad)))
        if not roles:
            err("%s roles 为空" % loc)

        if r.get("risk") not in VALID_RISK:
            err("%s risk=%r 不在 %s 内" % (loc, r.get("risk"), sorted(VALID_RISK)))

        if domains and r.get("domain") not in domains:
            err("%s domain=%r 不在 meta.domains 内" % (loc, r.get("domain")))

        # --- legal_basis ---
        bases = r.get("legal_basis") or []
        if not bases:
            err("%s legal_basis 为空" % loc)
        for j, b in enumerate(bases):
            bl = "%s legal_basis[%d]" % (loc, j)
            if not isinstance(b, dict):
                err("%s 不是 mapping" % bl)
                continue
            for f in BASIS_FIELDS:
                if not b.get(f):
                    err("%s 缺少 %s" % (bl, f))
            if b.get("quote_type") and b["quote_type"] not in VALID_QUOTE_TYPE:
                err("%s quote_type=%r 应为 原文/概括" % (bl, b["quote_type"]))
            ef = b.get("effective_from")
            if ef is not None:
                try:
                    d = ef if isinstance(ef, date) else date.fromisoformat(str(ef))
                    if d > date.today():
                        warn("%s 施行日期 %s 在未来" % (bl, d))
                except ValueError:
                    err("%s effective_from=%r 不是合法日期 (YYYY-MM-DD)" % (bl, ef))

    # --- backlog 不应与已有条目重叠 ---
    backlog = data.get("backlog") or []
    backlog_ids = set()
    for item in backlog:
        if isinstance(item, dict):
            backlog_ids.add(str(item.get("id", "")))
    overlap = backlog_ids & set(seen_ids)
    if overlap:
        err("backlog 与现有条目 ID 重叠: %s" % sorted(overlap))

    # --- 输出 ---
    for w in warnings:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)

    print("\n%d rules, %d warning(s), %d error(s)"
          % (len(rules), len(warnings), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
