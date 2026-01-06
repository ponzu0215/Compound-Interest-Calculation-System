from __future__ import annotations

# =========================================
# core.py（計算ロジック）
# 元HTML/JS: 資産複利計算ツール.html の script 部分を Python に移植
# 【重要】考え方・数式・分岐を変更しない（UIは別ファイル）
# =========================================

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import math

# ========================
# Utility Functions (JS移植)
# ========================

# JS: const monthsFromYM = (y, m) => (Number(y) * 12) + Number(m);
def months_from_ym(years: float, months: float) -> int:
    return int(float(years) * 12 + float(months))

# JS: const toMonthlyRate = (rAnnualPct) => { const r = Number(rAnnualPct) / 100; return Math.pow(1 + r, 1/12) - 1; };
def to_monthly_rate(r_annual_pct: float) -> float:
    r = float(r_annual_pct) / 100.0
    return (1.0 + r) ** (1.0 / 12.0) - 1.0

# JS: const toMonthlyInflation = (fAnnualPct) => { const f = Number(fAnnualPct) / 100; return Math.pow(1 + f, 1/12) - 1; };
def to_monthly_inflation(f_annual_pct: float) -> float:
    f = float(f_annual_pct) / 100.0
    return (1.0 + f) ** (1.0 / 12.0) - 1.0

# JS: const validYM = (m) => Number.isFinite(m) && m >= 0 && m <= 11;
def valid_ym(m: float) -> bool:
    return math.isfinite(m) and 0 <= m <= 11

# JS: function monthsToYearMonth(months) { ... }
def months_to_year_month(months: int) -> str:
    years = months // 12
    remaining = months % 12
    if years == 0:
        return f"{remaining}ヶ月"
    if remaining == 0:
        return f"{years}年"
    return f"{years}年{remaining}ヶ月"

# JS: const formatYen = (x) => { if (!isFinite(x)) return "—"; return Math.round(x).toLocaleString("ja-JP"); };
def format_yen(x: float) -> str:
    if not math.isfinite(x):
        return "—"
    return f"{int(round(x)):,}"

# ========================
# Accumulation Simulation (Annuity Due) - with initial gain
# ========================
@dataclass
class AccumulationSim:
    i: float
    n: int
    labels: List[str]
    principal_series: List[float]
    profit_series: List[float]
    total: float
    start_principal: float

# JS: function simulateAccumulation(rAnnual, currentValuation, currentGain, PMT, years, months) { ... }
def simulate_accumulation(r_annual: float, current_valuation: float, current_gain: float,
                          pmt: float, years: float, months: float) -> AccumulationSim:
    i = to_monthly_rate(r_annual)
    n = months_from_ym(years, months)

    # 現在の投資元本 = 評価額 - 評価損益額
    current_principal = float(current_valuation) - float(current_gain)

    balance = float(current_valuation)
    principal = float(current_principal)

    principal_series = [principal]
    profit_series = [float(current_gain)]
    labels = ["開始"]

    for t in range(1, n + 1):
        principal += float(pmt)
        balance += float(pmt)
        balance *= (1.0 + i)

        profit = balance - principal

        principal_series.append(principal)
        profit_series.append(profit)

        year_label = f"{t//12}年" if (t % 12 == 0) else ""
        labels.append(year_label)

    return AccumulationSim(i=i, n=n, labels=labels,
                           principal_series=principal_series,
                           profit_series=profit_series,
                           total=balance,
                           start_principal=current_principal)

# JS: function calcFutureValueAnnuityDue(rAnnual, currentValuation, PMT, years, months) { ... }
def calc_future_value_annuity_due(r_annual: float, current_valuation: float, pmt: float,
                                  years: float, months: float) -> float:
    i = to_monthly_rate(r_annual)
    n = months_from_ym(years, months)

    if n == 0:
        return float(current_valuation)

    if abs(i) < 1e-12:
        return float(current_valuation) + float(pmt) * n

    pow_ = (1.0 + i) ** n
    fv_p = float(current_valuation) * pow_
    fv_pmt = float(pmt) * ((pow_ - 1.0) / i) * (1.0 + i)
    return fv_p + fv_pmt

# ========================
# PMT Reverse (Annuity Due)
# ========================
# JS: function calcMonthlyContributionAnnuityDue(rAnnual, currentValuation, FVtarget, years, months) { ... }
def calc_monthly_contribution_annuity_due(r_annual: float, current_valuation: float, fv_target: float,
                                          years: float, months: float) -> float:
    i = to_monthly_rate(r_annual)
    n = months_from_ym(years, months)

    if n == 0:
        return 0.0

    if abs(i) < 1e-12:
        return (float(fv_target) - float(current_valuation)) / n

    pow_ = (1.0 + i) ** n
    fv_p = float(current_valuation) * pow_
    need = float(fv_target) - fv_p
    if need <= 0:
        return 0.0
    return need * i / ((1.0 + i) * (pow_ - 1.0))

# ========================
# Withdrawal with Tax Simulation
# ========================
# JS: function calcWithdrawalGross(rAnnual, PV, years, months) { ... }
def calc_withdrawal_gross(r_annual: float, pv: float, years: float, months: float) -> float:
    i = to_monthly_rate(r_annual)
    n = months_from_ym(years, months)

    if n == 0:
        return 0.0
    if abs(i) < 1e-12:
        return float(pv) / n

    return float(pv) * i / (1.0 - (1.0 + i) ** (-n))

@dataclass
class WithdrawalSim:
    i: float
    n: int
    gross: float
    labels: List[str]
    principal_series: List[float]
    profit_series: List[float]
    net_series: List[float]
    tax_series: List[float]

# JS: function simulateWithdrawalWithTax(rAnnual, PV, principalStart, years, months, taxRatePct) { ... }
def simulate_withdrawal_with_tax(r_annual: float, pv: float, principal_start: float,
                                 years: float, months: float, tax_rate_pct: float) -> WithdrawalSim:
    i = to_monthly_rate(r_annual)
    n = months_from_ym(years, months)
    tax = float(tax_rate_pct) / 100.0

    balance = float(pv)
    principal = min(float(principal_start), balance)
    if principal < 0:
        principal = 0.0

    gross = calc_withdrawal_gross(r_annual, pv, years, months)

    labels = ["開始"]
    principal_series = [principal]
    profit_series = [balance - principal]
    net_series = [0.0]
    tax_series = [0.0]

    for t in range(1, n + 1):
        balance *= (1.0 + i)
        profit_remaining = balance - principal

        withdraw = gross

        gain_ratio = 0.0
        if balance > 0 and profit_remaining > 0:
            gain_ratio = profit_remaining / balance

        taxable_gain = withdraw * gain_ratio
        tax_amount = taxable_gain * tax
        net = withdraw - tax_amount

        balance -= withdraw
        principal -= withdraw * (1.0 - gain_ratio)
        if principal < 0:
            principal = 0.0

        profit_remaining = max(balance - principal, 0.0)

        year_label = f"{t//12}年" if (t % 12 == 0) else ""
        labels.append(year_label)
        principal_series.append(principal)
        profit_series.append(profit_remaining)
        net_series.append(net)
        tax_series.append(tax_amount)

        if balance <= 0:
            break

    return WithdrawalSim(i=i, n=n, gross=gross, labels=labels,
                         principal_series=principal_series, profit_series=profit_series,
                         net_series=net_series, tax_series=tax_series)

# ========================
# Inflation Deflation
# ========================
# JS: function deflateNominalToReal(value, j, tMonths) { return value / Math.pow(1 + j, tMonths); }
def deflate_nominal_to_real(value: float, j: float, t_months: int) -> float:
    return float(value) / ((1.0 + float(j)) ** int(t_months))
