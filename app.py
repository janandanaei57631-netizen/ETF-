import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 24h全景天眼", layout="wide", initial_sidebar_state="expanded")
# 1分钟刷新一次 (数据量大，没必要30秒刷)
st_autorefresh(interval=60000, key="refresh_24h")

# CSS 样式 (红绿标签 + 滚动条美化)
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .status-bar { font-size: 0.8rem; color: #888; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now_cn = datetime.datetime.now(tz_cn).strftime("%H:%M")
    st.caption(f"当前时间: {now_cn}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    # 增加一个滑块，让你自己控制想看多少条新闻
    news_limit = st.slider("📊 显示新闻条数", min_value=20, max_value=100, value=50, step=10)
    
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

# --- 3. AI 分析 (并发单元) ---
def analyze_single_news(content):
    if not api_key: return ""
    try:
        # 极简Prompt，省流加速
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:80]}\n结论：【利好】xx 或 【利空】xx。6字内。"}],
            temperature=0.1, max_tokens=30
        )
        return res.choices[0].message.content.strip()
    except: return ""

# --- 4. 大数据获取 (Count 设为 100) ---
@st.cache_data(ttl=60) # 缓存60秒
def get_24h_data(limit_count):
    news = []
    
    # 源1: 金十数据 (抓取100条，覆盖24h)
    try:
        df_js = ak.js_news(count=limit_count + 20) # 多抓一点用来过滤
        for _, r in df_js.iterrows():
            t = str(r['time']) 
            # 格式化显示时间
            show_t = t[5:16] if len(t) > 16 else t # 显示 MM-DD HH:MM
            news.append({"t": t, "show_t": show_t, "txt": str(r['title']), "src": "Global"})
    except: pass

    # 源2: 财联社 (抓取最大量)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(limit_count)
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
    
    # 截取用户设定的数量 (比如 50 条)
    df = df.head(limit_count)

    # 开启 15 个线程加速分析 (应对大数据量)
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(analyze_single_news, df['txt'].tolist()))
    
    df['ai_result'] = results
    return df

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    # 状态栏
    tz_cn = pytz.timezone('Asia/Shanghai')
    update_time = datetime.datetime.now(tz_cn).strftime("%H:%M:%S")
    st.markdown(f"<div class='status-bar'>🔥 24小时全景 | 已抓取最新 {news_limit} 条情报 | 更新: {update_time}</div>", unsafe_allow_html=True)
    
    # 获取数据
    with st.spinner(f"正在全速扫描过去 24 小时的 {news_limit} 条新闻，请稍候..."):
        df = get_24h_data(news_limit)
    
    # 【核心升级】使用固定高度容器，实现“内部滚动”
    # height=800 意味着这个框固定 800像素高，内容多了会自动出滚动条
    with st.container(height=800):
        if not df.empty:
            for _, row in df.iterrows():
                # 原生容器，防乱码
                with st.container(border=True):
                    ans = row['ai_result']
                    tag_html = ""
                    if ans:
                        if "利好" in ans: tag_html = f'<span class="bull">🚀 {ans}</span>'
                        elif "利空" in ans: tag_html = f'<span class="bear">🧪 {ans}</span>'
                        elif "中性" in ans: tag_html = f'<span class="neutral">😐 {ans}</span>'
                        else: tag_html = f'<span class="neutral">🤖 {ans}</span>'
                    
                    # 显示：日期 时间 来源 标签
                    header = f"**{row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                    st.markdown(header, unsafe_allow_html=True)
                    st.write(row['txt'])
        else:
            st.warning("数据连接中... 请点击左侧红色按钮强制刷新")

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
