import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 稳定天眼", layout="wide", initial_sidebar_state="expanded")
# 更换 Key 强制清除之前的报错缓存
st_autorefresh(interval=60000, key="refresh_stable_final_v9")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .info-box { background-color: #262730; padding: 12px; border-radius: 5px; border-left: 5px solid #4ade80; margin-bottom: 20px; }
        .error-box { background-color: #3e2a2a; padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; color: #ccc; font-size: 0.9rem; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"北京时间: {now.strftime('%H:%M:%S')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    ai_limit = st.slider("🤖 AI 分析条数", 10, 60, 30)
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    if st.button("🔴 强制重启"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析 ---
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

# --- 4. 智能日期补全 (保留这个核心功能) ---
def clean_and_fix_date(t_str):
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    
    try:
        if len(t_str) <= 8: # 只有时间
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            dt = now.replace(hour=h, minute=m, second=0)
            # 如果时间比现在晚太多(超过30分钟)，说明是昨天的
            if dt > now + datetime.timedelta(minutes=30):
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif len(t_str) < 15 and "-" in t_str: # 只有月日
            return f"{now.year}-{t_str}" + (":00" if t_str.count(":")==1 else "")
        return t_str
    except:
        return t_str 

# --- 5. 数据获取 (回归稳定源) ---
@st.cache_data(ttl=60)
def get_stable_data(ai_count):
    news = []
    errors = []
    
    # 源1: 金十数据 (尝试抓 300 条，比较安全)
    try:
        df_js = ak.js_news(count=300) 
        for _, r in df_js.iterrows():
            news.append({"t_raw": str(r['time']), "txt": str(r['title']), "src": "Global"})
    except Exception as e: 
        errors.append(f"金十数据连接失败: {str(e)}")

    # 源2: 财联社 (回归最稳的 global_cls)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "CN"})
    except Exception as e:
        errors.append(f"财联社连接失败: {str(e)}")

    df = pd.DataFrame(news)
    
    # 如果完全没数据，返回空
    if df.empty: return df, errors

    # 1. 修复时间
    df['full_time'] = df['t_raw'].apply(clean_and_fix_date)
    
    # 2. 排序
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # 3. 截取 (保留300条，防止卡顿)
    df = df.head(300)
    
    # 4. 显示时间
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(x) > 16 else x)

    # 5. AI 分析
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_result'] = "" 

    # 仅当有数据需要分析时才开线程
    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_single_news, df_head['txt'].tolist()))
        df_head['ai_result'] = results
    
    final_df = pd.concat([df_head, df_tail])
    return final_df, errors

# --- 6. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    with st.spinner(f"正在连接稳定数据源..."):
        df, err_list = get_stable_data(ai_limit)
    
    # 错误提示区 (如果某一个源挂了，会在这里显示，而不是整个网页变红)
    if err_list:
        for err in err_list:
            st.markdown(f"<div class='error-box'>⚠️ {err}</div>", unsafe_allow_html=True)

    if not df.empty:
        start_t = df['full_time'].iloc[-1]
        end_t = df['full_time'].iloc[0]
        
        st.markdown(f"""
            <div class="info-box">
                <b>📊 实时监控中心</b><br>
                已加载情报：<b>{len(df)}</b> 条 <br>
                时间跨度：{start_t[5:16]} 至 {end_t[5:16]}
            </div>
        """, unsafe_allow_html=True)
        
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
        st.error("⚠️ 所有数据源暂时无法连接，可能是网络波动或接口限制，请稍后刷新。")

with col2:
    st.subheader("📊 核心标的")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        
        for _, r in my_spot.iterrows():
            val = float(r['涨跌幅'])
            st.metric(
                label=f"{r['名称']}",
                value=r['最新价'],
                delta=f"{val}%",
                delta_color="inverse"
            )
            st.divider()
    except:
        st.caption("行情加载中...")
