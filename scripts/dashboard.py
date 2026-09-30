import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="K4-L3B Day 13 Monitoring", layout="wide")

def load_data():
    log_file = Path("data/logs.jsonl")
    if not log_file.exists():
        return pd.DataFrame()
    
    records = []
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): 
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    df = pd.DataFrame(records)
    if df.empty:
        return df
    
    df['ts'] = pd.to_datetime(df['ts'])
    return df

def main():
    st.title("📊 K4-L3B Day 13 Monitoring & LLMOps Dashboard")
    
    df_raw = load_data()
    if df_raw.empty:
        st.warning("Không tìm thấy dữ liệu trong data/logs.jsonl.")
        return

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Tùy chọn hiển thị")
        time_mode = st.radio(
            "Phạm vi thời gian:",
            [
                "Phiên Incident (30 phút qua) - Khuyên dùng",
                "Toàn bộ lịch sử (All logs - 270+ records)",
                "60 phút gần nhất (Last 60m)"
            ],
            index=0
        )
        granularity = st.radio(
            "Độ phân giải biểu đồ:",
            [
                "15 giây (Thấy rõ đỉnh nhọn sự cố)",
                "1 phút (Chuẩn hợp đồng dashboard)"
            ],
            index=0
        )
        show_labels = st.checkbox("📌 Hiển thị con số chú thích (Data Labels)", value=True)
        
        if st.button("🔄 Refresh dữ liệu"):
            st.rerun()

    # Apply time filter
    max_time = df_raw['ts'].max()
    if time_mode.startswith("Phiên Incident"):
        df = df_raw[df_raw['ts'] >= (max_time - pd.Timedelta(minutes=30))].copy()
    elif time_mode.startswith("60 phút"):
        df = df_raw[df_raw['ts'] >= (max_time - pd.Timedelta(minutes=60))].copy()
    else:
        df = df_raw.copy()

    # Apply granularity bucket
    if "15 giây" in granularity:
        df['bucket'] = df['ts'].dt.floor('15s')
    else:
        df['bucket'] = df['ts'].dt.floor('1min')

    # Top KPI Banner
    df_resp_all = df[df['event'] == 'response_sent']
    total_req = len(df[df['event'] == 'request_received'])
    p95_lat = df_resp_all['latency_ms'].quantile(0.95) if not df_resp_all.empty else 0
    p50_lat = df_resp_all['latency_ms'].quantile(0.50) if not df_resp_all.empty else 0
    total_cost = df_resp_all['cost_usd'].sum() if 'cost_usd' in df_resp_all.columns else 0
    err_count = len(df[df['event'] == 'request_failed'])
    err_rate = (err_count / total_req * 100) if total_req > 0 else 0

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Tổng Requests", f"{total_req}")
    kpi2.metric("Latency P95", f"{p95_lat:.1f} ms", delta="> 2000 ms (ALERT!)" if p95_lat > 2000 else "Bình thường", delta_color="inverse")
    kpi3.metric("Latency P50", f"{p50_lat:.1f} ms")
    kpi4.metric("Tỉ lệ lỗi (Error Rate)", f"{err_rate:.1f}%")
    kpi5.metric("Tổng chi phí (USD)", f"${total_cost:.4f}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    # 1. Latency percentiles and TTFT
    with col1:
        st.subheader("1. Latency percentiles and TTFT")
        df_resp = df[df['event'] == 'response_sent'].copy()
        if not df_resp.empty:
            latency_agg = df_resp.groupby('bucket').agg(
                p50=('latency_ms', lambda x: x.quantile(0.50)),
                p95=('latency_ms', lambda x: x.quantile(0.95)),
                p99=('latency_ms', lambda x: x.quantile(0.99)),
                ttft_p95=('ttft_ms', lambda x: x.quantile(0.95))
            ).reset_index()
            
            latency_melt = latency_agg.melt('bucket', var_name='Metric', value_name='Latency (ms)')
            chart = alt.Chart(latency_melt).mark_line(point=True).encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('Latency (ms):Q', title='Độ trễ (ms)'),
                color=alt.Color('Metric:N', scale=alt.Scale(domain=['p50', 'p95', 'p99', 'ttft_p95'], range=['#4575b4', '#d73027', '#fc8d59', '#91bfdb'])),
                tooltip=['bucket:T', 'Metric:N', 'Latency (ms):Q']
            )
            
            rule = alt.Chart(pd.DataFrame({'y': [2000]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            rule_label = alt.Chart(pd.DataFrame({'y': [2000], 'label': ['Ngưỡng SLO: 2000 ms']})).mark_text(
                align='left', dx=5, dy=-6, color='red', fontWeight='bold', fontSize=11
            ).encode(y='y:Q', text='label:N')

            final_chart = chart + rule + rule_label
            if show_labels:
                p95_pts = latency_melt[latency_melt['Metric'] == 'p95']
                text_p95 = alt.Chart(p95_pts).mark_text(
                    align='center', baseline='bottom', dy=-8, fontSize=11, fontWeight='bold', color='#d73027'
                ).encode(
                    x='bucket:T',
                    y='Latency (ms):Q',
                    text=alt.Text('Latency (ms):Q', format='.0f')
                )
                final_chart = final_chart + text_p95

            st.altair_chart(final_chart, use_container_width=True)
            st.caption("🔴 Đường đứt nét đỏ: Ngưỡng Latency P95 cảnh báo sự cố (2000 ms)")
        else:
            st.write("Chưa có sự kiện response_sent.")

    # 2. Request traffic
    with col2:
        st.subheader("2. Request traffic")
        df_req = df[df['event'] == 'request_received'].copy()
        if not df_req.empty:
            traffic = df_req.groupby('bucket').size().reset_index(name='Requests')
            chart = alt.Chart(traffic).mark_bar(opacity=0.75, color='#1f77b4').encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('Requests:Q', title='Số lượng request'),
                tooltip=['bucket:T', 'Requests:Q']
            )
            rule = alt.Chart(pd.DataFrame({'y': [1]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            final_traffic = chart + rule
            if show_labels:
                text_traffic = alt.Chart(traffic).mark_text(
                    align='center', baseline='bottom', dy=-4, fontWeight='bold', fontSize=11, color='#1f77b4'
                ).encode(
                    x='bucket:T',
                    y='Requests:Q',
                    text='Requests:Q'
                )
                final_traffic = final_traffic + text_traffic
            st.altair_chart(final_traffic, use_container_width=True)
        else:
            st.write("Chưa có sự kiện request_received.")

    col3, col4 = st.columns(2)

    # 3. Error rate and retrieval success
    with col3:
        st.subheader("3. Error rate and retrieval success (%)")
        error_df = df[df['event'].isin(['request_received', 'request_failed'])].copy()
        tool_df = df[df['tool_success'].notnull()].copy()
        
        agg_data = []
        buckets = sorted(list(set(df['bucket'].dropna().unique())))
        
        for b in buckets:
            e_sub = error_df[error_df['bucket'] == b]
            req_count = len(e_sub[e_sub['event'] == 'request_received'])
            err_count = len(e_sub[e_sub['event'] == 'request_failed'])
            err_rate_b = (err_count / req_count * 100) if req_count > 0 else 0
            
            t_sub = tool_df[tool_df['bucket'] == b]
            total_tool = len(t_sub)
            success_tool = len(t_sub[t_sub['tool_success'] == True])
            tool_rate = (success_tool / total_tool * 100) if total_tool > 0 else 100.0
            
            agg_data.append({'bucket': b, 'Error Rate (%)': err_rate_b, 'Retrieval Success (%)': tool_rate})
            
        if agg_data:
            err_agg = pd.DataFrame(agg_data).melt('bucket', var_name='Metric', value_name='Percent')
            chart = alt.Chart(err_agg).mark_line(point=True).encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('Percent:Q', scale=alt.Scale(domain=[0, 115]), title='Phần trăm (%)'),
                color=alt.Color('Metric:N', scale=alt.Scale(domain=['Error Rate (%)', 'Retrieval Success (%)'], range=['#d62728', '#2ca02c'])),
                tooltip=['bucket:T', 'Metric:N', 'Percent:Q']
            )
            rule = alt.Chart(pd.DataFrame({'y': [2]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            rule_label = alt.Chart(pd.DataFrame({'y': [2], 'label': ['Ngưỡng Max: 2%']})).mark_text(
                align='left', dx=5, dy=-6, color='red', fontWeight='bold', fontSize=10
            ).encode(y='y:Q', text='label:N')

            final_err = chart + rule + rule_label
            if show_labels:
                text_err = alt.Chart(err_agg).mark_text(
                    align='center', baseline='bottom', dy=-6, fontSize=10, fontWeight='bold'
                ).encode(
                    x='bucket:T',
                    y='Percent:Q',
                    text=alt.Text('Percent:Q', format='.0f'),
                    color='Metric:N'
                )
                final_err = final_err + text_err
            st.altair_chart(final_err, use_container_width=True)
        else:
            st.write("Không có dữ liệu lỗi/retrieval.")

    # 4. Cost over time
    with col4:
        st.subheader("4. Cost over time (USD)")
        if not df_resp.empty and 'cost_usd' in df_resp.columns:
            cost_agg = df_resp.groupby('bucket')['cost_usd'].sum().reset_index()
            chart = alt.Chart(cost_agg).mark_bar(opacity=0.75, color='#2ca02c').encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('cost_usd:Q', title='Chi phí (USD)'),
                tooltip=['bucket:T', 'cost_usd:Q']
            )
            rule = alt.Chart(pd.DataFrame({'y': [2.5]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            final_cost = chart + rule
            if show_labels:
                text_cost = alt.Chart(cost_agg).mark_text(
                    align='center', baseline='bottom', dy=-4, fontWeight='bold', fontSize=10, color='#2ca02c'
                ).encode(
                    x='bucket:T',
                    y='cost_usd:Q',
                    text=alt.Text('cost_usd:Q', format='$.4f')
                )
                final_cost = final_cost + text_cost
            st.altair_chart(final_cost, use_container_width=True)
        else:
            st.write("Không có dữ liệu chi phí.")

    col5, col6 = st.columns(2)

    # 5. Input and output tokens
    with col5:
        st.subheader("5. Input and output tokens")
        if not df_resp.empty and 'tokens_in' in df_resp.columns and 'tokens_out' in df_resp.columns:
            token_agg = df_resp.groupby('bucket')[['tokens_in', 'tokens_out']].sum().reset_index()
            token_melt = token_agg.melt('bucket', var_name='Type', value_name='Tokens')
            chart = alt.Chart(token_melt).mark_line(point=True).encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('Tokens:Q', title='Số lượng token'),
                color=alt.Color('Type:N', scale=alt.Scale(domain=['tokens_in', 'tokens_out'], range=['#3182bd', '#e6550d'])),
                tooltip=['bucket:T', 'Type:N', 'Tokens:Q']
            )
            rule = alt.Chart(pd.DataFrame({'y': [50000]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            final_token = chart + rule
            if show_labels:
                text_token = alt.Chart(token_melt).mark_text(
                    align='center', baseline='bottom', dy=-6, fontSize=9, fontWeight='bold'
                ).encode(
                    x='bucket:T',
                    y='Tokens:Q',
                    text=alt.Text('Tokens:Q', format=',.0f'),
                    color='Type:N'
                )
                final_token = final_token + text_token
            st.altair_chart(final_token, use_container_width=True)
        else:
            st.write("Không có dữ liệu tokens.")

    # 6. Quality proxy
    with col6:
        st.subheader("6. Quality proxy")
        if not df_resp.empty and 'quality_score' in df_resp.columns:
            qual_agg = df_resp.groupby('bucket')['quality_score'].mean().reset_index()
            chart = alt.Chart(qual_agg).mark_line(point=True).encode(
                x=alt.X('bucket:T', title='Thời gian'),
                y=alt.Y('quality_score:Q', scale=alt.Scale(domain=[0, 1.15]), title='Điểm chất lượng'),
                tooltip=['bucket:T', 'quality_score:Q']
            )
            rule = alt.Chart(pd.DataFrame({'y': [0.75]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            rule_label = alt.Chart(pd.DataFrame({'y': [0.75], 'label': ['Ngưỡng Min: 0.75']})).mark_text(
                align='left', dx=5, dy=-6, color='red', fontWeight='bold', fontSize=10
            ).encode(y='y:Q', text='label:N')

            final_qual = chart + rule + rule_label
            if show_labels:
                text_qual = alt.Chart(qual_agg).mark_text(
                    align='center', baseline='bottom', dy=-6, fontSize=11, fontWeight='bold', color='#2ca02c'
                ).encode(
                    x='bucket:T',
                    y='quality_score:Q',
                    text=alt.Text('quality_score:Q', format='.2f')
                )
                final_qual = final_qual + text_qual
            st.altair_chart(final_qual, use_container_width=True)
        else:
            st.write("Không có dữ liệu quality.")

if __name__ == "__main__":
    main()
