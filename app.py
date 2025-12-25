import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 
import traceback 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 最终救援", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_fix_syntax_v2")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .debug-box { background-color: #222; color: #ff4b4b; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.8rem; margin-bottom: 10px; border: 1px solid #555; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⛑️ 救援控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"当前: {now.strftime('%H:%M:%S')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    ai_limit = st.slider("🤖 AI 分析条数", 10, 50, 20)
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    if st.button("🔴 强制重置缓存"):
        st.cache_data.clear()
        st.rerun()

# --- 3. 辅助函数 ---
def analyze_single_news(content):
    if not api_key: return ""
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:80]}\n结论：【利好】xx 或 【利空】xx。6字内。"}],
            temperature=0.1, max_tokens=30
        )
        return res.choices[0].message.content.strip()
    except Exception: return ""

def clean_and_fix_date(t_str):
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    try:
        if len(t_str) <= 8: 
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            dt = now.replace(hour=h, minute=m, second=0)
            if dt > now + datetime.timedelta(minutes=30):
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif len(t_str) < 15 and "-" in t_str: 
            return f"{now.year}-{t_str}" + (":00" if t_str.count(":")==1 else "")
        return t_str
    except:
        return t_str 

# 单独写一个函数处理时间显示，防止报错
def format_display_time(t_str):
    if len(t_str) > 16:
        return t_str[5:16]
    return t_str

# --- 4. 数据获取 ---
@st.cache_data(ttl=60)
def get_rescue_data(ai_count):
    news = []
    debug_logs = []
    
    # 尝试财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "CN"})
    except Exception as e:
        debug_logs.append(f"财联社报错: {str(e)}")

    # 尝试金十
    try:
        df_js = ak.js_news(count=300) 
        for _, r in df_js.iterrows():
            news.append({"t_raw": str(r['time']), "txt": str(r['title']), "src": "Global"})
    except Exception as e:
        debug_logs.append(f"金十报错: {str(e)}")

    df = pd.DataFrame(news)
    
    if df.empty: 
        return df, debug_logs

    # 数据处理
    df['full_time'] = df['t_raw'].apply(clean_and_fix_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(300)
    
    # 【修复点】这里不再用 lambda，改用函数，防止复制出错
    df['show_t'] = df['full_time'].apply(format_display_time)

    # AI 分析
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_result'] = "" 

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_single_news, df_head['txt'].tolist()))
        df_head['ai_result'] = results
    
    final_df = pd.concat([df_head, df_tail])
    return final_df, debug_logs

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    with st.spinner(f"正在进行最终数据连接..."):
        df, logs = get_rescue_data(ai_limit)
    
    # 显示报错（如果有）
    if logs:
        st.markdown("**⚠️ 调试日志 (截图给我看):**")
        for log in logs:
            st.markdown(f"<div class='debug-box'>{log}</div>", unsafe_allow_html=True)

    if not df.empty:
        count = len(df)
        st.success(f"✅ 成功连接！获取到 {count} 条数据")
        
        with st.container(height=800):
            for i, row in df.iterrows():
                with st.container(border=True):
                    ans = row['ai_result']
                    tag_html = ""
                    if ans:
                        if "利好" in ans: tag_html = f'<span class="bull">🚀 {ans}</span>'
                        elif "利空" in ans: tag_html = f'<span class="bear">🧪 {ans}</span>'
                        elif "中性" in ans: tag_html = f'<span class="neutral">😐 {ans}</span>'
                        else: tag_html = f'<span class="neutral">🤖 {ans}</span>'
                    else:
                        tag_html = f'<span class="history-tag">📜 历史</span>'
                    
                    header = f"**{row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                    st.markdown(header, unsafe_allow_html=True)
                    st.write(row['txt'])
    else:
        st.error("所有接口均未返回数据，请查看上方的调试日志。")

with col2:
    st.subheader("📊 核心标的")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        for _, r in my_spot.iterrows():
            val = float(r['涨跌幅'])
            st.metric(label=f"{r['名称']}", value=r['最新价'], delta=f"{val}%", delta_color="inverse")
            st.divider()
    except:
        st.caption("行情加载中...")
