import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz # 用于时区转换

# --- 1. 极速配置 ---
st.set_page_config(page_title="AI 极速实盘", layout="wide", initial_sidebar_state="expanded")

# 【关键修改】每 30 秒强制刷新一次页面，不给它偷懒的机会
st_autorefresh(interval=30000, key="refresh_realtime_v2")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .status-bar { font-size: 0.8rem; color: #888; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 控制台")
    
    # 获取当前北京时间
    tz_cn = pytz.timezone('Asia/Shanghai')
    now_cn = datetime.datetime.now(tz_cn).strftime("%H:%M:%S")
    st.caption(f"北京时间: {now_cn}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    # 红色按钮：手动强制拉取
    if st.button("🔴 立即强制刷新"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析 (单条) ---
def analyze_single_news(content):
    if not api_key: return ""
    try:
        # 极简模式，减少 Token 消耗，提高速度
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:80]}\n结论：【利好】xx 或 【利空】xx。6字内。"}],
            temperature=0.1, max_tokens=30
        )
        return res.choices[0].message.content.strip()
    except: return ""

# --- 4. 数据获取 (缓存仅15秒) ---
# 【关键修改】ttl=15，意味着每15秒它就会认为数据过期，必须重新去网上抓
@st.cache_data(ttl=15)
def get_realtime_data():
    news = []
    
    # 源1: 金十数据 (通常最快)
    try:
        df_js = ak.js_news(count=20)
        for _, r in df_js.iterrows():
            t = str(r['time']) # 格式通常是 YYYY-MM-DD HH:MM:SS
            # 简单处理时间显示
            show_t = t[11:16] if len(t) > 16 else t 
            news.append({"t": t, "show_t": show_t, "txt": str(r['title']), "src": "Global"})
    except: pass

    # 源2: 财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, r in df_cn.iterrows():
            t = str(r['发布时间'])
            show_t = t[11:16] if len(t) > 10 else t
            news.append({"t": t, "show_t": show_t, "txt": str(r['内容']), "src": "CN"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 排序：确保最新的在最上面
    df.sort_values(by='t', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(15) # 取前15条

    # 多线程 AI 分析
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_single_news, df['txt'].tolist()))
    
    df['ai_result'] = results
    return df

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    # 顶部状态栏：显示数据抓取时间，让你心中有数
    tz_cn = pytz.timezone('Asia/Shanghai')
    update_time = datetime.datetime.now(tz_cn).strftime("%H:%M:%S")
    st.markdown(f"<div class='status-bar'>🔥 实时情报 | 数据更新于: {update_time} (每30秒自动刷新)</div>", unsafe_allow_html=True)
    
    # 获取数据（不显示转圈圈，体验更好）
    df = get_realtime_data()
    
    if not df.empty:
        for _, row in df.iterrows():
            with st.container(border=True):
                ans = row['ai_result']
                # 标签生成
                tag_html = ""
                if ans:
                    if "利好" in ans: tag_html = f'<span class="bull">🚀 {ans}</span>'
                    elif "利空" in ans: tag_html = f'<span class="bear">🧪 {ans}</span>'
                    elif "中性" in ans: tag_html = f'<span class="neutral">😐 {ans}</span>'
                    else: tag_html = f'<span class="neutral">🤖 {ans}</span>'
                
                # 渲染
                header = f"**{row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                st.markdown(header, unsafe_allow_html=True)
                st.write(row['txt'])
    else:
        st.warning("正在连接数据源... 如果长时间无反应，请点击左侧红色按钮。")

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
