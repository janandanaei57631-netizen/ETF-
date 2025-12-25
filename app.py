import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 
import traceback # 用于打印报错详情

# --- 1. 基础配置 ---
# 【验证点】只要你看到标题变成 "AI 最终救援"，说明代码更新成功了！
st.set_page_config(page_title="AI 最终救援", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_rescue_v1")

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
    # 默认只分析10条，先保证能跑通
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
    
    # 红色按钮：强制重置
    if st.button("🔴 强制重置缓存"):
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

# --- 4. 智能日期补全 ---
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

# --- 5. 数据获取 (带详细报错) ---
@st.cache_data(ttl=60)
def get_rescue_data(ai_count):
    news = []
    debug_logs = [] # 记录报错信息
    
    # 源1: 财联社 (最稳的接口)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "CN"})
    except Exception as e:
        debug_logs.append(f"财联社接口报错: {str(e)}")

    # 源2: 金十数据 (尝试抓300条，如果不行为空)
    try:
        df_js = ak.js_news(count=300) 
        for _, r in df_js.iterrows():
            news.append({"t_raw": str(r['time']), "txt": str(r['title']), "src": "Global"})
    except Exception as e:
        debug_logs.append(f"金十数据报错: {str(e)}")

    df = pd.DataFrame(news)
    
    # 如果完全没有数据，返回错误日志
    if df.empty: 
        return df, debug_logs

    # 数据清洗
    df['full_time'] = df['t_raw'].apply(clean_and_fix_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(300)
    df['show_t'] = df['full_time'].apply(lambda x: x[5:1
