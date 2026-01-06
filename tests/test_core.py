from core import to_monthly_rate, calc_future_value_annuity_due, calc_monthly_contribution_annuity_due

def test_monthly_rate_zero():
    assert abs(to_monthly_rate(0.0)) < 1e-12

def test_fv_linear_when_rate_zero():
    fv = calc_future_value_annuity_due(0.0, 1000.0, 10.0, 1, 0)  # 12 months
    assert abs(fv - (1000.0 + 10.0 * 12)) < 1e-6

def test_pmt_zero_when_target_reachable():
    pmt = calc_monthly_contribution_annuity_due(5.0, 1_000_000.0, 500_000.0, 10, 0)
    assert pmt == 0.0
