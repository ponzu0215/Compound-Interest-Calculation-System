from __future__ import annotations
from typing import Optional, Tuple
import math
from core import valid_ym

def parse_number_text(value: str) -> float:
    # JS: parseFormattedNumber(value) = Number(value.replace(/,/g, ''));
    s = (value or "").replace(",", "").strip()
    if s == "":
        return 0.0
    return float(s)

def validate_common(years: float, months: float) -> Optional[str]:
    if not valid_ym(months):
        return "月は0〜11で入力してください。"
    if not math.isfinite(years) or years < 0:
        return "年は0以上の数値でお願いします。"
    return None
