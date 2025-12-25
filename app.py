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
st.set_page_config(page_title="AI 代码猎手", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_code_hunter_v1")

# CSS 样式 (重点增强了代码的显示)
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .news-card { 
            padding: 12px; margin-bottom: 12px; border-radius: 8px; 
            border: 1px solid #333; background-color: #1e1e1e;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        /* 顶部行布局 */
        .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
        .header-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        
        /* 标签系统 */
        .time-badge { color: #888; font-family: 'Consolas', monospace; font-size: 0.85rem; }
        
        /* 核心：代码标签 (高亮显示) */
        .tag-code { 
            background: #4a148c; /* 深紫色背景 */
            color: #e1bee7;     /* 亮紫色文字 */
            border: 1px solid #7b1fa2; 
            padding: 2px 8px; 
            border-radius: 4px; 
            font-family: 'Consolas', monospace; 
            font-size: 1rem;    /* 字体加大 */
            font-weight: bold; 
            letter-spacing: 1px;
            box-shadow: 0 0 5px rgba(123, 31, 162, 0.5); /* 发光效果 */
        }
        
        .tag-sector { background: #132438; color: #64b5f6; border: 1px solid #28446b; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        
        /* 强度标签 */
        .impact-high { color: #ff4b4b; font-weight: bold; font-size: 0.9rem; }
        .impact-low { color: #4ade80; font-weight: bold; font-size: 0.9rem; }
        
        .news-text { color: #e0e0e0; font-size: 0.95rem; line-height: 1.5; }
        
        /* 分栏表头 */
        .header-bull { color: #ff6b6b; border-bottom: 2px solid #ff6b6b; padding: 8px; margin-bottom: 12px; font-weight: bold; text-align: center; background: rgba(255, 75, 75, 0.1); border-radius: 6px; }
        .header-bear { color: #4ade80; border-bottom: 2px solid #4ade80; padding: 8px; margin-bottom: 12px; font-weight: bold; text-align: center; background: rgba(74, 222, 128, 0.1); border-radius: 6px; }
        
        /* 历史列表 */
        .history-row { display: flex; align-items: baseline; padding: 8px 5px; border-bottom: 1px solid #262626; }
        .hist-time { flex: 0 0 110px; color: #666; font-family: monospace; font-size: 0.85rem; }
        .hist-txt { flex: 1; color: #bbb; font-size: 0.9rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 深海控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"Server: {now.strftime('%H:%M:%S')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    ai_limit = st.slider("🤖 深度扫描条数", 10, 60, 20)
    
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

# --- 3. 核心：增强型 AI 提示词 ---
def analyze_deep_prediction(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # ⚠️ 这里是关键修改：强制要求 AI 联想代码
        prompt = f"""
        作为资深交易员，分析这条新闻：{content[:150]}
        
        请严格按格式输出：方向|板块|代码|强度
        
        1.方向：利好/利空/中性
        2.板块：如"光刻机"，越细越好
        3.代码：【必须填】最相关的A股/港股/美股代码。
           - 如果新闻没写代码，请根据公司名联想（如"茅台"->600519，"特斯拉"->TSLA）。
           - 如果是宏观消息（如降息），填相关的ETF代码（如510300）。
           - 只有完全找不到时才填"无"。
        4.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无影响
        
        示例：利好|白酒|600519|大涨
        """
        
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=60
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) >= 4:
            return {
                "dir": parts[0].strip(),
                "sector": parts[1].strip(),
                "code": parts[2].strip(), # 这里现在会尽可能有值
                "impact": parts[3].strip()
            }
        return None
    except: return None

# --- 4. 时间清洗 ---
def clean_date(t_str):
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    try:
        if len(t_str) <= 8:
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            dt = now.replace(hour=h, minute=m, second=s)
            if dt > now + datetime.timedelta(minutes=30): dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        if "-" in t_str and ":" in t_str: return t_str
        return str(now)
    except: return str(now)

# --- 5. 多源抓取 ---
def fetch_sina():
    try:
        df = ak.stock_info_global_sina()
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
        return data
    except: return []

def fetch_em():
    try:
        # 抓取 500 条
        df = ak.stock_news_em(symbol="全部").head(500)
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
        return data
    except: return []

def fetch_cls():
    try:
        df = ak.stock_info_global_cls(symbol="全部")
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
        return data
    except: return []

@st.cache_data(ttl=60)
def get_hunter_data(ai_count):
    all_news = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(fetch_sina)
        f2 = executor.submit(fetch_em)
        f3 = executor.submit(fetch_cls)
        all_news.extend(f1.result())
        all_news.extend(f2.result())
        all_news.extend(f3.result())
        
    df = pd.DataFrame(all_news)
    if df.empty: return df

    df['full_time'] = df['t'].apply(clean_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    # 保留 12 小时级的数据量
    df = df.head(800)
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(str(x))>16 else str(x))

    # AI 分析
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_data'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(analyze_deep_prediction, df_head['txt'].tolist()))
        df_head['ai_data'] = results
    
    return pd.concat([df_head, df_tail])

# --- 6. 渲染卡片 (增强代码显示) ---
def render_card(row):
    ai = row['ai_data']
    html_tags = ""
    
    if ai:
        # 1. 代码标签 (最重要，放最前或显眼位置)
        if ai['code'] and ai['code'] != "无":
            html_tags += f"<span class='tag-code'>{ai['code']}</span> "
            
        # 2. 板块
        if ai['sector'] and ai['sector'] != "无":
            html_tags += f"<span class='tag-sector'>{ai['sector']}</span> "
            
        # 3. 强度 (带颜色)
        imp = ai['impact']
        if "暴涨" in imp or "大涨" in imp: 
            html_tags += f"<span class='impact-high'>🔥 {imp}</span>"
        elif "暴跌" in imp or "大跌" in imp: 
            html_tags += f"<span class='impact-low'>🟢 {imp}</span>"
    
    st.markdown(
        f"""
        <div class="news-card">
            <div class="card-header">
                <div class="header-left">
                    <span class="time-badge">{row['show_t']}</span>
                    {html_tags}
                </div>
            </div>
            <div class="news-text">{row['txt']}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- 7. 主界面 ---
col_main, col_quote = st.columns([3, 1]) 

with col_main:
    with st.spinner("🚀 正在全网检索代码与信号..."):
        df = get_hunter_data(ai_limit)
    
    if not df.empty:
        t_start = df['full_time'].iloc[0]
        t_end = df['full_time'].iloc[-1]
        
        # 顶部统计
        st.markdown(f"""
            <div style="background:#111; padding:8px; border-radius:5px; margin-bottom:15px; border:1px solid #333; color:#666; font-size:0.85rem; display:flex; justify-content:space-between;">
                <span>已扫描: <b style="color:#ddd">{len(df)}</b> 条情报</span>
                <span>范围: {t_start[5:16]} ~ {t_end[5:16]}</span>
            </div>
        """, unsafe_allow_html=True)

        df_analyzed = df[df['ai_data'].notnull()]
        
        bull_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利好' in x['dir'])]
        bear_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利空' in x['dir'])]
        
        exclude = list(bull_df.index) + list(bear_df.index)
        rest_df = df[~df.index.isin(exclude)]
        
        c_bull, c_bear = st.columns(2)
        with c_bull:
            st.markdown(f"<div class='header-bull'>🔥 红色·利好 ({len(bull_df)})</div>", unsafe_allow_html=True)
            if not bull_df.empty:
                for _, r in bull_df.iterrows(): render_card(r)
            else: st.info("暂无")
        
        with c_bear:
            st.markdown(f"<div class='header-bear'>🟢 绿色·利空 ({len(bear_df)})</div>", unsafe_allow_html=True)
            if not bear_df.empty:
                for _, r in bear_df.iterrows(): render_card(r)
            else: st.info("暂无")
        
        st.markdown(f"<div style='margin-top:20px; border-top:1px solid #333; padding-top:10px; color:#888; font-weight:bold;'>📜 历史信息流 ({len(rest_df)})</div>", unsafe_allow_html=True)
        with st.container(height=600):
            for _, row in rest_df.iterrows():
                st.markdown(
                    f"""
                    <div class="history-row">
                        <div class="hist-time">{row['show_t']}</div>
                        <div class="hist-txt">{row['txt']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    else:
        st.error("数据连接超时，请重试")

with col_quote:
    st.subheader("📊 核心持仓")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        for _, r in my_spot.iterrows():
            val = float(r['涨跌幅'])
            st.metric(label=f"{r['名称']}", value=r['最新价'], delta=f"{val}%", delta_color="inverse")
            st.divider()
    except: st.caption("行情加载中...")
