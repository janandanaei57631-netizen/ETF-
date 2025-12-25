import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 交易员 (原生版)", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="refresh_native_v1")

# 只保留最基本的 CSS (用于 AI 标签的颜色)，不再用它做排版
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚙️ 控制台")
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
        st.success("✅ AI 引擎在线")
    else:
        client = None
        st.error("❌ 密钥未连接")
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="如 512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    # 强制刷新按钮
    if st.button("🔄 刷新数据"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析 ---
def analyze(content):
    if not client: return "❌无Key"
    try:
        # 极简指令
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:100]}\n只回结论：【利好】xx 或 【利空】xx。8字内。"}],
            temperature=0.1, max_tokens=40
        )
        return res.choices[0].message.content.strip()
    except: return "⚠️超时"

# --- 4. 数据获取 ---
@st.cache_data(ttl=180)
def get_data_native():
    news = []
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, r in df_cn.iterrows():
            t = str(r['发布时间'])
            news.append({"t": t, "show_t": t[11:16] if len(t)>10 else t, "txt": str(r['内容']), "src": "CN"})
    except: pass
    
    try:
        df_js = ak.js_news(count=20)
        for _, r in df_js.iterrows():
            t = str(r['time'])
            news.append({"t": t, "show_t": t[11:16] if len(t)>10 else t, "txt": str(r['title']), "src": "Global"})
    except: pass

    df = pd.DataFrame(news)
    if not df.empty:
        df.sort_values(by='t', ascending=False, inplace=True)
        df.drop_duplicates(subset=['txt'], inplace=True)
        return df.head(15)
    return pd.DataFrame()

# --- 5. 主界面 (原生组件布局) ---
col1, col2 = st.columns([2.5, 1])

with col1:
    st.subheader("🔥 实时情报")
    df = get_data_native()
    
    if not df.empty:
        for i, (idx, row) in enumerate(df.iterrows()):
            # 【核心修改】使用 st.container(border=True) 代替 HTML 盒子
            # 这是一个原生的带边框的盒子，绝对稳固
            with st.container(border=True):
                
                # 1. 准备 AI 标签
                tag_html = ""
                if i < 6:
                    ans = analyze(row['txt'])
                    if "利好" in ans:
                        tag_html = f'<span class="bull">🚀 {ans}</span>'
                    elif "利空" in ans:
                        tag_html = f'<span class="bear">🧪 {ans}</span>'
                    elif "中性" in ans:
                        tag_html = f'<span class="neutral">😐 {ans}</span>'
                    else:
                        tag_html = f'<span class="neutral">🤖 {ans}</span>'
                
                # 2. 顶部信息栏：时间 + 来源 + AI标签
                # 使用 markdown 拼接，但结构很简单，不容易出错
                header_str = f"**⏱️ {row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                st.markdown(header_str, unsafe_allow_html=True)
                
                # 3. 新闻内容 (直接打印，防止乱码)
                st.write(row['txt'])
                
    else:
        st.info("数据加载中...")

with col2:
    st.subheader("📊 核心标的")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        
        for _, r in my_spot.iterrows():
            # 原生指标组件
            val = float(r['涨跌幅'])
            st.metric(
                label=f"{r['名称']} ({r['代码']})",
                value=r['最新价'],
                delta=f"{val}%",
                delta_color="inverse" # 红涨绿跌
            )
            st.divider() # 分割线
    except:
        st.caption("行情连接中...")
