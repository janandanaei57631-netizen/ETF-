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
st.set_page_config(page_title="AI 东方财富版", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_em_v1")

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
    st.header("⚡ 控制台")
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
    
    if st.button("🔴 强制重置"):
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
        # 东方财富的时间格式通常是 "2024-12-25 14:30:00"
        if len(t_str) > 10:
            return t_str
        # 如果只有时间
        if len(t_str) <= 8: 
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            dt = now.replace(hour=h, minute=m, second=0)
            if dt > now + datetime.timedelta(minutes=30):
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return t_str
    except:
        return str(now)

def format_show_time(x):
    # 只显示 月-日 时:分
    s = str(x)
    if len(s) > 16:
        return s[5:16]
    return s

# --- 4. 数据获取 (替换为东方财富) ---
@st.cache_data(ttl=60)
def get_data_em(ai_count):
    news = []
    debug_logs = []
    
    # 源1: 东方财富 (替代了报错的金十)
    try:
        # stock_news_em 接口非常稳定
        df_em = ak.stock_news_em(symbol="全部")
        # 只要前 300 条
        df_em = df_em.head(300)
        for _, r in df_em.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
    except Exception as e:
        debug_logs.append(f"东方财富报错: {str(e)}")

    # 源2: 财联社 (辅助)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "CN"})
    except Exception as e:
        debug_logs.append(f"财联社报错: {str(e)}")

    df = pd.DataFrame(news)
    
    if df.empty: 
        return df, debug_logs

    # 数据清洗
    df['full_time'] = df['t_raw'].apply(clean_and_fix_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # 保留 300 条
    df = df.head(300)
    
    # 格式化时间
    df['show_t'] = df['full_time'].apply(format_show_time)

    # AI 分析 Top N
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
    with st.spinner(f"正在连接东方财富数据源..."):
        df, logs = get_data_em(ai_limit)
    
    if logs:
        st.markdown("**⚠️ 调试日志:**")
        for log in logs:
            st.markdown(f"<div class='debug-box'>{log}</div>", unsafe_allow_html=True)

    if not df.empty:
        count = len(df)
        st.success(f"✅ 成功连接！获取到 {count} 条情报 (已剔除报错源)")
        
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
        st.error("所有数据源均无法连接，请截图发给我。")

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
