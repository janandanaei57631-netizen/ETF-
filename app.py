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
st.set_page_config(page_title="AI 极速多空", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_fast_v1")

# CSS 样式
st.markdown("""
    <style>
        .news-card { padding: 10px; margin-bottom: 8px; border-radius: 6px; border: 1px solid #333; background-color: #1a1a1a; }
        .time-badge { color: #f1c40f; font-family: monospace; font-weight: bold; font-size: 0.85rem; }
        .src-badge { background: #333; color: #999; padding: 1px 4px; border-radius: 3px; font-size: 0.7rem; border: 1px solid #444; }
        .tag-sector { background: #182236; color: #64b5f6; border: 1px solid #2d4675; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; }
        .tag-code { background: #221836; color: #b39ddb; border: 1px solid #45306b; padding: 1px 5px; border-radius: 3px; font-family: monospace; font-size: 0.8rem; font-weight: bold; }
        .tag-impact { font-size: 0.8rem; font-weight: bold; margin-left: 4px; }
        .news-text { color: #ccc; font-size: 0.9rem; line-height: 1.45; }
        .header-bull { color: #ff4b4b; border-bottom: 2px solid #ff4b4b; padding-bottom: 5px; margin-bottom: 10px; font-weight: bold; text-align: center; background: rgba(255, 75, 75, 0.1); border-radius: 4px; }
        .header-bear { color: #4ade80; border-bottom: 2px solid #4ade80; padding-bottom: 5px; margin-bottom: 10px; font-weight: bold; text-align: center; background: rgba(74, 222, 128, 0.1); border-radius: 4px; }
        .header-neutral { color: #888; border-top: 1px solid #333; padding-top: 15px; margin-top: 20px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 极速控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"Server: {now.strftime('%H:%M:%S')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 就绪")
    else:
        api_key = None
        st.error("❌ 无密钥")
    
    st.divider()
    # 默认调低到 15 条，保证速度
    ai_limit = st.slider("🤖 分析条数", 10, 50, 15)
    
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

# --- 3. 核心功能函数 ---

def analyze_deep_prediction(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        # 极简 Prompt
        prompt = f"""
        分析：{content[:120]}
        格式：方向|板块|代码|强度
        方向：利好/利空/中性
        板块：如光伏，无则填无
        代码：如600519，无则填无
        强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无影响
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=50
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) >= 4:
            return {"dir": parts[0].strip(), "sector": parts[1].strip(), "code": parts[2].strip(), "impact": parts[3].strip()}
        return None
    except: return None

def clean_date(t_str):
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    try:
        if len(t_str) <= 8:
            parts = t_str.split(":")
            dt = now.replace(hour=int(parts[0]), minute=int(parts[1]), second=0)
            if dt > now + datetime.timedelta(minutes=30): dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return t_str
    except: return str(now)

# --- 4. 并行数据抓取 (速度优化的关键) ---

def fetch_sina():
    try:
        df = ak.stock_info_global_sina()
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
        return data
    except: return []

def fetch_em():
    try:
        df = ak.stock_news_em(symbol="全部").head(200)
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
        return data
    except: return []

def fetch_cls():
    try:
        df = ak.stock_info_global_cls(symbol="全部").head(50)
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
        return data
    except: return []

@st.cache_data(ttl=60)
def get_parallel_data(ai_count):
    # 1. 并行抓取数据 (三个线程同时跑)
    all_news = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(fetch_sina)
        f2 = executor.submit(fetch_em)
        f3 = executor.submit(fetch_cls)
        
        # 等待结果
        all_news.extend(f1.result())
        all_news.extend(f2.result())
        all_news.extend(f3.result())
        
    df = pd.DataFrame(all_news)
    if df.empty: return df

    # 2. 数据清洗
    df['full_time'] = df['t'].apply(clean_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(400)
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(str(x))>16 else str(x))

    # 3. AI 分析
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_data'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(analyze_deep_prediction, df_head['txt'].tolist()))
        df_head['ai_data'] = results
    
    return pd.concat([df_head, df_tail])

# --- 5. 渲染函数 ---
def render_card(row):
    ai = row['ai_data']
    html_tags = ""
    if ai:
        if ai['sector'] and ai['sector'] != "无": html_tags += f"<span class='tag-sector'>📂 {ai['sector']}</span> "
        if ai['code'] and ai['code'] != "无": html_tags += f"<span class='tag-code'>{ai['code']}</span> "
        imp = ai['impact']
        imp_c = "#ccc"
        if "暴涨" in imp or "大涨" in imp: imp_c = "#ff4b4b"
        elif "暴跌" in imp or "大跌" in imp: imp_c = "#4ade80"
        if imp != "无影响": html_tags += f"<span class='tag-impact' style='color:{imp_c}'>⚡ {imp}</span>"
    
    st.markdown(
        f"""
        <div class="news-card">
            <div style="margin-bottom:4px;">
                <span class="time-badge">{row['show_t']}</span>
                <span class="src-badge">{row['src']}</span>
                {html_tags}
            </div>
            <div class="news-text">{row['txt']}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- 6. 主界面 ---
col_main, col_quote = st.columns([3, 1]) 

with col_main:
    # 进度条占位符
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("🚀 正在启动 3 线程并发抓取...")
    progress_bar.progress(10)
    
    # 真正的获取数据
    df = get_parallel_data(ai_limit)
    
    progress_bar.progress(90)
    status_text.text("⚡ 渲染界面中...")
    
    # 清除进度条
    time.sleep(0.5)
    progress_bar.empty()
    status_text.empty()
    
    if not df.empty:
        df_analyzed = df[df['ai_data'].notnull()]
        
        # 容错过滤
        bull_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利好' in x['dir'])]
        bear_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利空' in x['dir'])]
        
        exclude_indices = list(bull_df.index) + list(bear_df.index)
        rest_df = df[~df.index.isin(exclude_indices)]
        
        c_bull, c_bear = st.columns(2)
        
        with c_bull:
            st.markdown(f"<div class='header-bull'>🔥 利好 ({len(bull_df)})</div>", unsafe_allow_html=True)
            if not bull_df.empty:
                for _, row in bull_df.iterrows(): render_card(row)
            else: st.caption("暂无")
                
        with c_bear:
            st.markdown(f"<div class='header-bear'>🟢 利空 ({len(bear_df)})</div>", unsafe_allow_html=True)
            if not bear_df.empty:
                for _, row in bear_df.iterrows(): render_card(row)
            else: st.caption("暂无")
        
        st.markdown(f"<div class='header-neutral'>😐 历史 / 中性消息</div>", unsafe_allow_html=True)
        with st.container(height=500):
            for _, row in rest_df.head(100).iterrows(): 
                st.markdown(f"<div style='border-bottom:1px solid #222; padding:6px 0; font-size:0.9rem; color:#888;'><span style='color:#666; font-family:monospace; margin-right:10px;'>{row['show_t']}</span>{row['txt']}</div>", unsafe_allow_html=True)

    else:
        st.error("数据连接超时，请点击左侧红色按钮重试")

with col_quote:
    st.subheader("📊 持仓")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        for _, r in my_spot.iterrows():
            val = float(r['涨跌幅'])
            st.metric(label=f"{r['名称']}", value=r['最新价'], delta=f"{val}%", delta_color="inverse")
            st.divider()
    except: st.caption("行情加载中...")
