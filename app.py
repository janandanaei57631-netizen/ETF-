import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 24h时光机", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_time_machine")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .status-bar { font-size: 0.8rem; color: #888; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now_cn = datetime.datetime.now(tz_cn).strftime("%m-%d %H:%M")
    st.caption(f"当前: {now_cn}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    # 这里的滑块控制“AI 分析多少条”，而不是“显示多少条”
    ai_limit = st.slider("🤖 AI 深度分析条数", 20, 100, 50, step=10, help="分析太多会变慢，建议50条")
    st.info("📉 下方会自动加载 300-500 条历史新闻以覆盖24小时")
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    if st.button("🔴 强制刷新"):
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
    except: return ""

# --- 4. 24小时数据获取 ---
@st.cache_data(ttl=60)
def get_massive_data(ai_count):
    news = []
    
    # 1. 金十数据：暴力抓取 400 条 (覆盖24小时的核心)
    try:
        df_js = ak.js_news(count=400) 
        for _, r in df_js.iterrows():
            t = str(r['time']) 
            show_t = t[5:16] if len(t) > 16 else t 
            news.append({"t": t, "show_t": show_t, "txt": str(r['title']), "src": "Global"})
    except: pass

    # 2. 财联社：尽力抓取 (通常只有最新几十条)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            t = str(r['发布时间'])
            show_t = t[5:16] if len(t) > 10 else t
            news.append({"t": t, "show_t": show_t, "txt": str(r['内容']), "src": "CN"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 排序 & 去重
    df.sort_values(by='t', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # --- 核心逻辑：切分数据 ---
    # Top N 条：送去给 AI 分析
    df_head = df.head(ai_count).copy()
    
    # 剩下的：作为历史记录 (不分析)
    df_tail = df.iloc[ai_count:].head(300).copy() # 再取300条历史，防止页面太卡
    df_tail['ai_result'] = "" # 历史数据没有 AI 结果

    # 并发分析 Top N
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_single_news, df_head['txt'].tolist()))
    df_head['ai_result'] = results
    
    # 合并回去
    final_df = pd.concat([df_head, df_tail])
    
    return final_df

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    # 获取数据
    with st.spinner(f"正在回溯过去 24 小时的数据流..."):
        df = get_massive_data(ai_limit)
    
    count_total = len(df)
    st.markdown(f"<div class='status-bar'>🔥 24H 舆情回放 | 共加载 {count_total} 条情报 | 前 {ai_limit} 条含 AI 分析</div>", unsafe_allow_html=True)
    
    # 滚动容器
    with st.container(height=850):
        if not df.empty:
            for i, row in df.iterrows():
                with st.container(border=True):
                    ans = row['ai_result']
                    
                    # 标签逻辑
                    tag_html = ""
                    if ans:
                        # 有 AI 结果 (最新的新闻)
                        if "利好" in ans: tag_html = f'<span class="bull">🚀 {ans}</span>'
                        elif "利空" in ans: tag_html = f'<span class="bear">🧪 {ans}</span>'
                        elif "中性" in ans: tag_html = f'<span class="neutral">😐 {ans}</span>'
                        else: tag_html = f'<span class="neutral">🤖 {ans}</span>'
                    else:
                        # 无 AI 结果 (历史新闻)
                        tag_html = f'<span class="history-tag">📜 历史消息</span>'
                    
                    header = f"**{row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                    st.markdown(header, unsafe_allow_html=True)
                    st.write(row['txt'])
        else:
            st.warning("暂无数据，请检查网络")

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
