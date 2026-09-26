"""养护机械业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
OPTIONAL_FIELDS = ["停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
STATUS_ORDER = ["待保养", "可用", "保养中", "已报废"]
ACTION_RULES = {"安排保养": "保养中", "确认可用": "可用", "报废机械": "已报废"}
NEGATIVE_ACTIONS = []

SCRAPPED_STATUS = "已报废"
IN_MAINTENANCE_STATUS = "保养中"
LAST_MAINTAINED_FIELD = "上次保养日"
NEXT_MAINTENANCE_FIELD = "下次保养日"
DUE_FIELD = "保养到期"
VERDICT_FIELD = "保养结论"
DATE_MISSING_TEXT = "保养日期不全，暂无法判断是否到期"


def _parse_day(value: Any) -> date | None:
    """把字段值解析成日期；空值或非法格式一律按缺失处理。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def maintenance_verdict(entry: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """保养到期判断的唯一口径：列表、详情页、统计卡都从这里取结论。

    判定顺序固定：已报废 → 保养中 → 日期缺失 → 下次保养日与今天比较；
    上次保养日、下次保养日缺任何一个都回同一句话，不再各写一套。
    """
    today = today or date.today()
    status = str(entry.get("status") or "")
    if status == SCRAPPED_STATUS:
        return {DUE_FIELD: False, VERDICT_FIELD: "已报废，不再安排保养"}
    if status == IN_MAINTENANCE_STATUS:
        return {DUE_FIELD: False, VERDICT_FIELD: "保养中，无需重复安排"}
    last_day = _parse_day(entry.get(LAST_MAINTAINED_FIELD))
    next_day = _parse_day(entry.get(NEXT_MAINTENANCE_FIELD))
    if last_day is None or next_day is None:
        return {DUE_FIELD: False, VERDICT_FIELD: DATE_MISSING_TEXT}
    if next_day <= today:
        return {DUE_FIELD: True, VERDICT_FIELD: "保养已到期，需要安排保养"}
    return {DUE_FIELD: False, VERDICT_FIELD: "未到保养期"}


class EquipService:
    @staticmethod
    def _with_verdict(row: dict[str, Any], today: date) -> dict[str, Any]:
        """给记录附上保养结论；返回副本，不把派生字段写回库里的原始行。"""
        return {**row, **maintenance_verdict(row, today)}

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机械编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        today = date.today()
        return [self._with_verdict(row, today) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return self._with_verdict(row, date.today())

    def maintenance_stats(self) -> list[dict[str, Any]]:
        """统计卡口径：与列表、详情页共用 maintenance_verdict，台数自然一致。"""
        rows = store.rows(MODULE)
        today = date.today()
        return [
            {"label": "在册机械", "value": sum(1 for row in rows if row.get("status") != SCRAPPED_STATUS)},
            {"label": "待保养机械", "value": sum(1 for row in rows if maintenance_verdict(row, today)[DUE_FIELD])},
            {"label": "保养中机械", "value": sum(1 for row in rows if row.get("status") == IN_MAINTENANCE_STATUS)},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        code = str(values.get("机械编号") or "").strip()
        for row in rows:
            if str(row.get("机械编号") or "").strip() == code:
                # 重复提交：返回已存在的那一条，不再新增记录
                return self._with_verdict(row, date.today()), [], False
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry.update({field: values.get(field) for field in OPTIONAL_FIELDS if values.get(field) is not None})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._with_verdict(entry, date.today()), [], True

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护机械 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护机械可执行范围"
        if action == "安排保养" and entry.get("status") == SCRAPPED_STATUS:
            return None, f"养护机械 {entry_id} 已报废，不再安排保养"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._with_verdict(entry, date.today()), f"养护机械已{action}"
