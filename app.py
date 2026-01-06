from __future__ import annotations

import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import textwrap

from core import (
    simulate_accumulation,
    calc_future_value_annuity_due,
    calc_monthly_contribution_annuity_due,
    simulate_withdrawal_with_tax,
    to_monthly_inflation,
    deflate_nominal_to_real,
    months_from_ym,
    months_to_year_month,
    format_yen,
)
from validations import parse_number_text, validate_common
from ui import inject_css, page_header, page_footer

st.set_page_config(page_title="投資複利計算システム", layout="centered")

inject_css()

# ===== 状態保持（タブ切替でも入力/結果を保持）=====
# Streamlitは操作のたびにスクリプトを再実行するため、入力値（key付きtext_input）は自動で session_state に残ります。
# ここでは「計算結果（表示HTML・グラフ）」もタブごとに保存して、タブ移動しても完全に復元できるようにします。
for _k in ("saved_fv", "saved_pmt", "saved_wd"):
    if _k not in st.session_state:
        st.session_state[_k] = None

# ③の「①の結果から引き継ぐ」で使う最小データ
if "last_future" not in st.session_state:
    st.session_state.last_future = None

page_header()

tabs = ["① 将来の運用資産額", "② 毎月の積立額", "③ 取り崩し可能額"]
st.markdown('<div class="mz-tabbar">', unsafe_allow_html=True)
choice = st.radio("", tabs, horizontal=True)
st.markdown("</div>", unsafe_allow_html=True)


# -------------------------
# 入力の桁区切り（text_inputをカンマ表記に整形）
# ※計算は parse_number_text（カンマ除去）で行うため、ロジックは不変
# -------------------------
def _format_number_inplace(key: str) -> None:
    s = st.session_state.get(key, "")
    if s is None:
        return
    s = str(s).strip()
    if s == "":
        return
    raw = s.replace(",", "").replace(" ", "")
    sign = ""
    if raw.startswith("-"):
        sign = "-"
        raw = raw[1:]
    if "." in raw:
        int_part, dec_part = raw.split(".", 1)
    else:
        int_part, dec_part = raw, ""
    if int_part == "" or (not int_part.isdigit()):
        return
    formatted_int = f"{int(int_part):,}"
    if dec_part != "":
        st.session_state[key] = f"{sign}{formatted_int}.{dec_part}"
    else:
        st.session_state[key] = f"{sign}{formatted_int}"

def stacked_area_chart(labels, principal, profit):
    # 見やすさ改善：インタラクティブ（ホバー表示）対応（計算ロジックは不変）
    # - 横軸ラベル非表示 / タイトルなし
    # - 積み上げ折れ線（下：元本、上：利益）
    # - 凡例（元本/利益）を大きく
    # - ホバーで「投資◯年◯ヶ月目 / 利益（構成比） / 元本（構成比） / 合計」を表示
    n = len(principal)
    x = list(range(n))

    total = [p + g for p, g in zip(principal, profit)]
    profit_top = [p + g for p, g in zip(principal, profit)]

    ym_label = [f"投資{idx//12}年{idx%12}ヶ月目" for idx in x]

    principal_pct = [((p / t) * 100.0 if t else 0.0) for p, t in zip(principal, total)]
    profit_pct = [((g / t) * 100.0 if t else 0.0) for g, t in zip(profit, total)]

    color_principal = "#2f5fd0"
    color_profit = "#8b5cf6"

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=principal,
            mode="lines",
            name="元本",
            line=dict(color=color_principal, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(47,95,208,0.35)",
            hoverinfo="skip",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=profit_top,
            mode="lines",
            name="利益",
            line=dict(color=color_profit, width=2.5),
            fill="tonexty",
            fillcolor="rgba(139,92,246,0.30)",
            customdata=list(zip(ym_label, principal, profit, total, principal_pct, profit_pct)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "<b>利益</b>: %{customdata[2]:,.0f} 円（%{customdata[5]:.1f}%）<br>"
                "<b>元本</b>: %{customdata[1]:,.0f} 円（%{customdata[4]:.1f}%）<br>"
                "<b>合計</b>: %{customdata[3]:,.0f} 円"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=380,
        margin=dict(l=22, r=22, t=12, b=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=16),
        ),
        hovermode="x",
        hoverlabel=dict(
            font=dict(size=16, color="#111827"),
            bgcolor="rgba(255,255,255,0.98)",
            bordercolor="rgba(17,24,39,0.25)",
            align="left",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
    )

    fig.update_xaxes(showticklabels=False, title=None, zeroline=False, showgrid=False)
    fig.update_yaxes(tickformat=",", title=None, zeroline=False, gridcolor="rgba(0,0,0,0.08)")

    return fig

def result_block(html: str):
    # NOTE: Avoid Streamlit/Markdown treating indented HTML as code blocks
    safe = textwrap.dedent(html)
    safe = "\n".join(line.lstrip() for line in safe.splitlines()).strip()
    st.markdown(f'<div class="result">{safe}</div>', unsafe_allow_html=True)

def result_item(label, value, highlight=False):
    cls = "result-item highlight" if highlight else "result-item"
    # 先頭のインデントがMarkdownのコードブロック扱いにならないよう、改行/インデント無しで返す
    return (
        f'<div class="{cls}">'
        f'<div class="result-label">{label}</div>'
        f'<div class="result-value">{value}</div>'
        f'</div>'
    )

# -------------------------
# Page 1: Future Asset Value
# -------------------------
if choice == tabs[0]:
    st.markdown('<div class="calculator-card">', unsafe_allow_html=True)
    st.markdown("<h2>📈 将来の運用資産額を計算</h2>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        fv_rate = st.text_input("年間運用利回り（%）", value="", key="fv_rate")
    with c2:
        fv_inflation = st.text_input("インフレ率（%）", value="", key="fv_inflation")

    c1, c2 = st.columns(2)
    with c1:
        fv_valuation = st.text_input("現在の投資額：評価額（円）", value="", key="fv_valuation", on_change=_format_number_inplace, args=("fv_valuation",))
    with c2:
        fv_gain = st.text_input("現在の投資額：評価損益額（円）", value="", key="fv_gain", on_change=_format_number_inplace, args=("fv_gain",))

    # auto principal
    try:
        principal_now = parse_number_text(fv_valuation) - parse_number_text(fv_gain)
    except Exception:
        principal_now = 0.0

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("現在の投資元本（自動計算）（円）", value=format_yen(principal_now), disabled=True)
    with c2:
        fv_monthly = st.text_input("毎月の積立額（円）", value="", key="fv_monthly", on_change=_format_number_inplace, args=("fv_monthly",))

    c1, c2 = st.columns(2)
    with c1:
        fv_years = st.text_input("積立期間（年）", value="", key="fv_years")
    with c2:
        fv_months = st.text_input("積立期間（月）※0-11", value="", key="fv_months")

    if st.button("計算する", type="primary", key="btn_fv_calc"):
        try:
            r = parse_number_text(fv_rate)
            inf = parse_number_text(fv_inflation)
            valuation = parse_number_text(fv_valuation)
            gain = parse_number_text(fv_gain)
            pmt = parse_number_text(fv_monthly)
            years = parse_number_text(fv_years)
            months = parse_number_text(fv_months)

            err = validate_common(years, months)
            if err:
                st.error(err)
            else:
                sim = simulate_accumulation(r, valuation, gain, pmt, years, months)
                fv = sim.total
                principal_total = sim.start_principal + pmt * sim.n
                profit = fv - principal_total
                profit_rate = (profit / principal_total) * 100 if principal_total != 0 else 0.0

                j = to_monthly_inflation(inf)
                fv_real = deflate_nominal_to_real(fv, j, sim.n)

                st.session_state.last_future = {"FV": fv, "principalTotal": principal_total, "rate": r, "inflation": inf}

                html = f'''
                <div style="display:grid; gap:15px;">
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("将来資産（名目）", f"¥{format_yen(fv)}", highlight=True)}
                    {result_item("利益率", f"{profit_rate:.1f} %", highlight=True)}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:15px;">
                    {result_item("将来資産（実質）", f"¥{format_yen(fv_real)}")}
                    {result_item("元本合計", f"¥{format_yen(principal_total)}")}
                    {result_item("利益", f"¥{format_yen(profit)}")}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("期間", months_to_year_month(sim.n))}
                    {result_item("実効月利", f"{(sim.i*100):.4f} %")}
                  </div>
                </div>
                '''
                fig = stacked_area_chart(sim.labels, sim.principal_series, sim.profit_series)

                # タブ移動しても復元できるように保存
                st.session_state.saved_fv = {"html": html, "fig": fig}
        except Exception as e:
            st.error(f"入力は数値でお願いします。 ({e})")


    # --- 保存済みの計算結果を表示（タブ移動後も復元） ---
    if st.session_state.get("saved_fv"):
        saved = st.session_state.saved_fv
        result_block(saved["html"])
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.plotly_chart(saved["fig"], use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="note">※月初積立（期首払い）で計算しています。税金・手数料は考慮していません。<br>※実質価値はインフレ率で購買力ベースに割り戻した値です。</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Page 2: Monthly Investment
# -------------------------
elif choice == tabs[1]:
    st.markdown('<div class="calculator-card">', unsafe_allow_html=True)
    st.markdown("<h2>💵 毎月の積立額を計算（逆算）</h2>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        pmt_rate = st.text_input("年間運用利回り（%）", value="", key="pmt_rate")
    with c2:
        pmt_inflation = st.text_input("インフレ率（%）", value="", key="pmt_inflation")

    c1, c2 = st.columns(2)
    with c1:
        pmt_valuation = st.text_input("現在の投資額：評価額（円）", value="", key="pmt_valuation", on_change=_format_number_inplace, args=("pmt_valuation",))
    with c2:
        pmt_gain = st.text_input("現在の投資額：評価損益額（円）", value="", key="pmt_gain", on_change=_format_number_inplace, args=("pmt_gain",))

    try:
        principal_now = parse_number_text(pmt_valuation) - parse_number_text(pmt_gain)
    except Exception:
        principal_now = 0.0

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("現在の投資元本（自動計算）（円）", value=format_yen(principal_now), disabled=True)
    with c2:
        pmt_target = st.text_input("目標資産額（円）", value="", key="pmt_target", on_change=_format_number_inplace, args=("pmt_target",))

    c1, c2 = st.columns(2)
    with c1:
        pmt_years = st.text_input("積立期間（年）", value="", key="pmt_years")
    with c2:
        pmt_months = st.text_input("積立期間（月）※0-11", value="", key="pmt_months")

    if st.button("計算する", type="primary", key="btn_pmt_calc"):
        try:
            r = parse_number_text(pmt_rate)
            inf = parse_number_text(pmt_inflation)
            valuation = parse_number_text(pmt_valuation)
            gain = parse_number_text(pmt_gain)
            target = parse_number_text(pmt_target)
            years = parse_number_text(pmt_years)
            months = parse_number_text(pmt_months)

            err = validate_common(years, months)
            if err:
                st.error(err)
            else:
                current_principal = valuation - gain
                pmt = calc_monthly_contribution_annuity_due(r, valuation, target, years, months)
                fv = calc_future_value_annuity_due(r, valuation, pmt, years, months)

                n = months_from_ym(years, months)
                principal_total = current_principal + pmt * n
                profit = fv - principal_total
                profit_rate = (profit / principal_total) * 100 if principal_total != 0 else 0.0

                j = to_monthly_inflation(inf)
                fv_real = deflate_nominal_to_real(fv, j, n)

                note = "目標は初期投資＋運用だけで達成可能です。" if pmt <= 0 else "—"

                html = f'''
                <div style="display:grid; gap:15px;">
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("必要な毎月積立", f"¥{format_yen(pmt)}", highlight=True)}
                    {result_item("補足", note)}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:15px;">
                    {result_item("到達資産（名目）", f"¥{format_yen(fv)}")}
                    {result_item("到達資産（実質）", f"¥{format_yen(fv_real)}")}
                    {result_item("元本合計", f"¥{format_yen(principal_total)}")}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("利益", f"¥{format_yen(profit)}")}
                    {result_item("利益率", f"{profit_rate:.1f} %")}
                  </div>
                </div>
                '''
                sim = simulate_accumulation(r, valuation, gain, pmt, years, months)
                fig = stacked_area_chart(sim.labels, sim.principal_series, sim.profit_series)

                # タブ移動しても復元できるように保存
                st.session_state.saved_pmt = {"html": html, "fig": fig}
        except Exception as e:
            st.error(f"入力は数値でお願いします。 ({e})")


    # --- 保存済みの計算結果を表示（タブ移動後も復元） ---
    if st.session_state.get("saved_pmt"):
        saved = st.session_state.saved_pmt
        result_block(saved["html"])
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.plotly_chart(saved["fig"], use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="note">※月初積立（期首払い）です。目標が初期投資＋運用だけで達成可能な場合、積立は0円表示になります。</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Page 3: Monthly Withdrawal
# -------------------------
else:
    st.markdown('<div class="calculator-card">', unsafe_allow_html=True)
    st.markdown("<h2>🏦 毎月の取り崩し可能額を計算</h2>", unsafe_allow_html=True)

    if st.button("🔁 ①の結果から元本/資産を引き継ぐ", type="primary", key="btn_wd_inherit"):
        if not st.session_state.last_future:
            st.warning("①を先に計算してください。")
        else:
            lf = st.session_state.last_future
            st.session_state.wd_rate = str(lf.get("rate", 0))
            st.session_state.wd_inflation = str(lf.get("inflation", 0))
            st.session_state.wd_assets = str(int(round(lf.get("FV", 0))))
            st.session_state.wd_principal = str(int(round(lf.get("principalTotal", 0))))

    c1, c2 = st.columns(2)
    with c1:
        wd_rate = st.text_input("年間運用利回り（%）", value=st.session_state.get("wd_rate", ""), key="wd_rate")
    with c2:
        wd_inflation = st.text_input("インフレ率（%）", value=st.session_state.get("wd_inflation", ""), key="wd_inflation")

    c1, c2 = st.columns(2)
    with c1:
        wd_assets = st.text_input("運用資産額（円）", value=st.session_state.get("wd_assets", ""), key="wd_assets", on_change=_format_number_inplace, args=("wd_assets",))
    with c2:
        wd_principal = st.text_input("取り崩し開始時点の元本（円）", value=st.session_state.get("wd_principal", ""), key="wd_principal", on_change=_format_number_inplace, args=("wd_principal",))

    c1, c2 = st.columns(2)
    with c1:
        wd_years = st.text_input("利用年数（年）", value="", key="wd_years")
    with c2:
        wd_months = st.text_input("利用年数（月）※0-11", value="", key="wd_months")

    c1, c2 = st.columns(2)
    with c1:
        wd_tax = st.text_input("税率（%）", value="20.315", key="wd_tax")
    with c2:
        st.write("")

    if st.button("計算する", type="primary", key="btn_wd_calc"):
        try:
            r = parse_number_text(wd_rate)
            inf = parse_number_text(wd_inflation)
            pv = parse_number_text(wd_assets)
            principal_start = parse_number_text(wd_principal)
            years = parse_number_text(wd_years)
            months = parse_number_text(wd_months)
            tax_rate = parse_number_text(wd_tax)

            err = validate_common(years, months)
            if err:
                st.error(err)
            elif any((not isinstance(v, float) and not isinstance(v, int)) for v in [r, inf, pv, principal_start, years, tax_rate]):
                st.error("入力は数値でお願いします。")
            elif pv < 0 or principal_start < 0 or tax_rate < 0:
                st.error("入力は0以上の数値でお願いします。")
            elif tax_rate > 100:
                st.error("税率は100%以下で入力してください。")
            else:
                sim = simulate_withdrawal_with_tax(r, pv, principal_start, years, months, tax_rate)

                gross = sim.gross
                n = len(sim.labels) - 1

                avg_tax = sum(sim.tax_series[1:]) / (n or 1)
                avg_net = sum(sim.net_series[1:]) / (n or 1)

                j = to_monthly_inflation(inf)
                avg_net_real = sum(deflate_nominal_to_real(v, j, t + 1) for t, v in enumerate(sim.net_series[1:])) / (n or 1)

                total_withdrawal = gross * n
                total_profit = total_withdrawal - principal_start
                profit_rate = (total_profit / principal_start) * 100 if principal_start != 0 else 0.0

                html = f'''
                <div style="display:grid; gap:15px;">
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("平均手取り（名目）", f"¥{format_yen(avg_net)}", highlight=True)}
                    {result_item("利益率", f"{profit_rate:.1f} %", highlight=True)}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:15px;">
                    {result_item("毎月取り崩し（税引前）", f"¥{format_yen(gross)}")}
                    {result_item("平均税額", f"¥{format_yen(avg_tax)}")}
                    {result_item("平均手取り（実質）", f"¥{format_yen(avg_net_real)}")}
                  </div>
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    {result_item("期間", months_to_year_month(months_from_ym(years, months)))}
                    {result_item("税率", f"{tax_rate:.3f} %")}
                  </div>
                </div>
                '''
                fig = stacked_area_chart(sim.labels, sim.principal_series, sim.profit_series)

                # タブ移動しても復元できるように保存
                st.session_state.saved_wd = {"html": html, "fig": fig}
        except Exception as e:
            st.error(f"入力は数値でお願いします。 ({e})")


    # --- 保存済みの計算結果を表示（タブ移動後も復元） ---
    if st.session_state.get("saved_wd"):
        saved = st.session_state.saved_wd
        result_block(saved["html"])
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.plotly_chart(saved["fig"], use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="note">※取り崩しは月末（期末払い）で一定額、運用しながら減らす前提です。<br>※課税は「資産全体を同率で比例売却する簡易モデル」で、毎月の利益比率に応じて税額を算出します。</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

page_footer()