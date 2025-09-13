from typing import Tuple, Dict, Any

PAGES_BONUS_ORDER = 15
PENALTY_WRONG_JUZ_OTHER = 8
PENALTY_WRONG_QUARTER_OTHER = 6
PENALTY_EMPTY_JUZ = 5
PENALTY_EMPTY_QUARTER = 4
FAIL_THRESHOLD = 50


class GradingService:
    """خدمة مساعدة لإدارة تقييم مواضع الصفحات"""

    def __init__(self, request):
        self.request = request

    # الحالة الداخلية للتقييم
    def state(self) -> Dict[str, Any]:
        st = self.request.session.get("pages_grade") or {}
        st.setdefault("bonus", 0)
        st.setdefault("penalty", 0)
        st.setdefault("events", [])
        st.setdefault("order_set", False)
        self.request.session["pages_grade"] = st
        return st

    # إضافة حدث للتقييم (زيادة أو نقصان)
    def push(self, text: str, delta: int) -> Tuple[int, int]:
        st = self.state()
        if delta >= 0:
            st["bonus"] = min(100, int(st.get("bonus", 0)) + int(delta))
        else:
            st["penalty"] = min(100, int(st.get("penalty", 0)) + int(-delta))
        st["events"].insert(0, {"t": text, "d": int(delta)})
        self.request.session["pages_grade"] = st
        score = max(0, min(100, 100 - int(st["penalty"]) + int(st["bonus"])))
        return int(score), int(delta)

    # الحصول على الدرجة الحالية
    def get(self) -> Tuple[int, Dict[str, Any]]:
        st = self.state()
        score = max(0, min(100, 100 - int(st.get("penalty", 0)) + int(st.get("bonus", 0))))
        return int(score), st

    # تمييز اختيار بالترتيب
    def mark_order(self) -> Tuple[int, Dict[str, Any]]:
        st = self.state()
        if not st.get("order_set"):
            st["order_set"] = True
            self.request.session["pages_order"] = True
            self.push("اختيار بالترتيب (Bonus)", +PAGES_BONUS_ORDER)
        return self.get()


__all__ = [
    "GradingService",
    "PAGES_BONUS_ORDER",
    "PENALTY_WRONG_JUZ_OTHER",
    "PENALTY_WRONG_QUARTER_OTHER",
    "PENALTY_EMPTY_JUZ",
    "PENALTY_EMPTY_QUARTER",
    "FAIL_THRESHOLD",
]
