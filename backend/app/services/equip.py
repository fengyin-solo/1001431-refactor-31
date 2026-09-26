"""养护机械业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
STATUS_ORDER = ["待保养", "可用", "保养中", "已报废"]
ACTION_RULES = {"安排保养": "保养中", "确认可用": "可用", "报废机械": "已报废"}
NEGATIVE_ACTIONS: list[str] = []

SCRAPPED_STATUS = "已报废"
LAST_MAINTAINED_FIELD = "上次保养日"
NEXT_MAINTENANCE_FIELD = "下次保养日"
MISSING_DATE_MESSAGE = "上次保养日或下次保养日未登记齐全，暂无法判断保养是否到期"
SCRAPPED_MESSAGE = "机械已报废，不再安排保养"
VERDICT_STATES = ["保养到期", "保养未到期", "日期待补", "已报废"]


def _parse_day(value: Any) -> date | None:
    """把字段值解析成日期；空值或格式不对都按未登记处理。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def maintenance_verdict(row: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """保养到期的唯一口径：列表、详情、统计卡都从这一个函数取结论。

    - 已报废：不再排进保养，直接给报废结论；
    - 上次保养日、下次保养日缺任意一个：用同一句话交代，不计入待保养；
    - 两个日期齐全：下次保养日不晚于今天即为保养到期。
    """
    if row.get("status") == SCRAPPED_STATUS:
        return {"due": False, "state": "已报废", "message": SCRAPPED_MESSAGE}
    last_day = _parse_day(row.get(LAST_MAINTAINED_FIELD))
    next_day = _parse_day(row.get(NEXT_MAINTENANCE_FIELD))
    if last_day is None or next_day is None:
        return {"due": False, "state": "日期待补", "message": MISSING_DATE_MESSAGE}
    due = next_day <= (today or date.today())
    if due:
        message = f"下次保养日 {next_day.isoformat()} 已到期，请安排保养"
    else:
        message = f"下次保养日 {next_day.isoformat()} 未到，暂不需要保养"
    return {"due": due, "state": "保养到期" if due else "保养未到期", "message": message}


def _with_verdict(row: dict[str, Any]) -> dict[str, Any]:
    """给记录附上保养结论与说明；返回副本，避免污染仓库里的原始数据。"""
    verdict = maintenance_verdict(row)
    return {**row, "保养结论": verdict["state"], "保养说明": verdict["message"]}


class EquipService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        verdict: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机械编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if verdict:
            rows = [row for row in rows if maintenance_verdict(row)["state"] == verdict]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_with_verdict(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return _with_verdict(entry)

    def stats(self) -> list[dict[str, Any]]:
        """统计卡口径：与列表、详情共用 maintenance_verdict，台数自然一致。"""
        rows = store.rows(MODULE)
        return [
            {"label": "在册机械", "value": sum(1 for row in rows if row.get("status") != SCRAPPED_STATUS)},
            {"label": "待保养机械", "value": sum(1 for row in rows if maintenance_verdict(row)["due"])},
            {"label": "保养中机械", "value": sum(1 for row in rows if row.get("status") == "保养中")},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        code = str(values.get("机械编号") or "").strip()
        for row in rows:
            if str(row.get("机械编号", "")).strip() == code:
                return _with_verdict(row), [], False
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _with_verdict(entry), [], True

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护机械 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护机械可执行范围"
        if action == "安排保养" and entry.get("status") == SCRAPPED_STATUS:
            return None, SCRAPPED_MESSAGE
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _with_verdict(entry), f"养护机械已{action}"
