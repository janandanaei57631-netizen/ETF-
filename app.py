import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 24h全景", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_stable_v1")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .count-badge { font-size: 1.2rem; font-weight: bold; color: #f1c40f; }
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

# --- 3. AI 分析函数 (修复了报错点) ---
def analyze_single_news(content):
    # 检查 Key 是否存在
    if not api_key:
        return ""
    
    # 这里使用了完整的 try-except 结构，防止报错
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content[:80]}\n结论：【利好】xx 或 【利空】xx。6字内。"}],
            temperature=0.1,
            max_tokens=30
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return ""

# --- 4. 数据获取 ---
@st.cache_data(ttl=60)
def get_history_data_v3(ai_count):
    news = []
    
    # 1. 金十数据
    try:
        df_js = ak.js_news(count=500) 
        for _, r in df_js.iterrows():
            t = str(r['time']) 
            show_t = t[5:16] if len(t) > 16 else t 
            news.append({"t": t, "show_t": show_t, "txt": str(r['title']), "src": "Global"})
    except:
        pass

    # 2. 财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            t = str(r['发布时间'])
            show_t = t[5:16] if len(t) > 10 else t
            news.append({"t": t, "show_t": show_t, "txt": str(r['内容']), "src": "CN"})
    except:
        pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 排序
    df.sort_values(by='t', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # 截取
    df = df.head(400)
    
    # 切分
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_result'] = "" 

    # 并发
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_single_news, df_head['txt'].tolist()))
    df_head['ai_result'] = results
    
    # 合并
    final_df = pd.concat([df_head, df_tail])
    
    return final_df

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    with st.spinner(f"正在拉取数据..."):
        df = get_history_data_v3(ai_limit)
    
    count_total = len(df)
    
    st.markdown(f"""
        <div style="margin-bottom:10px; border-bottom:1px solid #333; padding-bottom:10px;">
            <span class="count-badge">{count_total}</span> 条情报已加载 
            <span style="color:#888; font-size:0.9rem;">(包含过去24小时)</span>
        </div>
    """, unsafe_allow_html=True)
    
    with st.container(height=850):
        if not df.empty:
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
            st.warning("暂无数据")

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
