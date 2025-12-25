import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 
import time

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 24H 全覆盖", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_24h_final")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .time-badge { font-family: monospace; color: #f1c40f; font-weight: bold; }
        .source-sina { background-color: #e67e22; color: white; padding: 2px 4px; border-radius: 3px; font-size: 0.7rem; }
        .source-em { background-color: #3498db; color: white; padding: 2px 4px; border-radius: 3px; font-size: 0.7rem; }
        .source-cls { background-color: #e74c3c; color: white; padding: 2px 4px; border-radius: 3px; font-size: 0.7rem; }
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
    # 默认分析 30 条，剩下的只看
    ai_limit = st.slider("🤖 AI 分析最新 N 条", 10, 100, 30)
    
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

def clean_date(t_str):
    # 统一清洗时间格式为 YYYY-MM-DD HH:MM:SS
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    try:
        # 1. 只有时间 "14:30"
        if len(t_str) <= 5: 
             t_str += ":00"
        
        # 2. 只有时间 "14:30:00"
        if len(t_str) <= 8:
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            dt = now.replace(hour=h, minute=m, second=0)
            if dt > now + datetime.timedelta(minutes=30): # 跨日判断
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. 完整时间
        return t_str
    except:
        return str(now)

# --- 4. 多源数据获取 (人海战术) ---
@st.cache_data(ttl=60)
def get_combined_data(ai_count):
    news = []
    
    # ---------------------------
    # 源1: 新浪财经 7x24 (Global)
    # ---------------------------
    try:
        # 抓取 500 条
        df_sina = ak.stock_info_global_sina() 
        # 新浪返回的列名通常是：时间, 内容
        for _, r in df_sina.iterrows():
            # 新浪的时间通常带日期，质量较高
            news.append({"t_raw": str(r['时间']), "txt": str(r['内容']), "src": "新浪", "badge": "source-sina"})
    except: pass

    # ---------------------------
    # 源2: 东方财富 (Eastmoney)
    # ---------------------------
    try:
        # 抓取 300 条
        df_em = ak.stock_news_em(symbol="全部")
        df_em = df_em.head(300)
        for _, r in df_em.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财", "badge": "source-em"})
    except: pass

    # ---------------------------
    # 源3: 财联社 (Cailian)
    # ---------------------------
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "财联", "badge": "source-cls"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 统一清洗时间
    df['full_time'] = df['t_raw'].apply(clean_date)
    
    # 排序：最新的在上面
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # --- 截断逻辑
