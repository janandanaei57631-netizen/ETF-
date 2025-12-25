import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures # 引入多线程工具

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 交易员 (全量极速版)", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="refresh_turbo_v1")

# CSS 样式
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
        # 注意：这里只创建 client，具体调用在函数里
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success("✅ AI 引擎在线 (多线程模式)")
    else:
        api_key = None
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
    
    if st.button("🔄 强制刷新"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析函数 (独立调用) ---
def analyze_single_news(content):
    if not api_key: return "❌无Key"
    try:
        # 每次调用都新建临时的 client，确保线程安全
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:100]}\n只回结论：【利好】xx 或 【利空】xx。8字内。"}],
            temperature=0.1, max_tokens=40
        )
        return res.choices[0].message.content.strip()
    except:
        return ""

# --- 4. 数据获取 & 并行分析 ---
@st.cache_data(ttl=180)
def get_analyzed_data():
    news = []
    # 1. 获取数据
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(15)
        for _, r in df_cn.iterrows():
            t = str(r['发布时间'])
            news.append({"t": t, "show_t": t[11:16] if len(t)>10 else t, "txt": str(r['内容']), "src": "CN"})
    except: pass
    
    try:
        df_js = ak.js_news(count=15)
        for _, r in df_js.iterrows():
            t = str(r['time'])
            news.append({"t": t, "show_t": t[11:16] if len(t)>10 else t, "txt": str(r['title']), "src": "Global"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 2. 数据清洗
    df.sort_values(by='t', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(15) # 取前15条

    # 3. 【核心升级】多线程并行分析
    # 使用 ThreadPoolExecutor 同时分析所有新闻
    txt_list = df['txt'].tolist()
    results = []
    
    # 开启 10 个线程同时跑
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_single_news, txt_list))
    
    # 把 AI 结果塞回表格
    df['ai_result'] = results
    return df

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    st.subheader("🔥 实时情报 (全量分析)")
    
    # 加个加载提示，因为虽然快，但也要等几秒
    with st.spinner("AI 正在同时阅读 15 条新闻..."):
        df = get_analyzed_data()
    
    if not df.empty:
        for _, row in df.iterrows():
            with st.container(border=True):
                # 获取预先算好的 AI 结果
                ans = row['ai_result']
                
                # 生成标签
                tag_html = ""
                if ans:
                    if "利好" in ans:
                        tag_html = f'<span class="bull">🚀 {ans}</span>'
                    elif "利空" in ans:
                        tag_html = f'<span class="bear">🧪 {ans}</span>'
                    elif "中性" in ans:
                        tag_html = f'<span class="neutral">😐 {ans}</span>'
                    else:
                        tag_html = f'<span class="neutral">🤖 {ans}</span>'
                
                # 顶部栏
                header_str = f"**⏱️ {row['show_t']}** &nbsp; `{row['src']}` &nbsp; {tag_html}"
                st.markdown(header_str, unsafe_allow_html=True)
                
                # 正文
                st.write(row['txt'])
    else:
        st.info("暂无数据或连接超时，请点击左侧刷新...")

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
        st.caption("行情连接中...")
