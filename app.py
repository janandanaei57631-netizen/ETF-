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
st.set_page_config(page_title="AI 12H 深海挖掘", layout="wide", initial_sidebar_state="expanded")
# 1分钟刷新一次
st_autorefresh(interval=60000, key="refresh_deep_12h_v1")

# CSS 样式 (保持上一版的高颜值)
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .news-card { 
            padding: 12px; margin-bottom: 10px; border-radius: 8px; 
            border: 1px solid #333; background-color: #1e1e1e;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .time-badge { color: #f1c40f; font-family: 'Consolas', monospace; font-weight: bold; font-size: 0.9rem; }
        .src-badge { background: #333; color: #aaa; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid #444; }
        .tag-sector { background: #132438; color: #64b5f6; border: 1px solid #28446b; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        .tag-code { background: #241b36; color: #d1c4e9; border: 1px solid #513b7a; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.85rem; font-weight: bold; }
        .tag-impact { font-size: 0.85rem; font-weight: bold; margin-left: 6px; }
        .news-text { color: #e0e0e0; font-size: 0.95rem; line-height: 1.5; margin-top: 5px; }
        
        .header-bull { color: #ff6b6b; border-bottom: 2px solid #ff6b6b; padding-bottom: 8px; margin-bottom: 12px; font-size: 1.1rem; font-weight: bold; text-align: center; background: rgba(255, 75, 75, 0.08); border-radius: 6px; }
        .header-bear { color: #4ade80; border-bottom: 2px solid #4ade80; padding-bottom: 8px; margin-bottom: 12px; font-size: 1.1rem; font-weight: bold; text-align: center; background: rgba(74, 222, 128, 0.08); border-radius: 6px; }
        
        .history-container { margin-top: 20px; border-top: 1px solid #333; padding-top: 10px; }
        .history-title { color: #888; font-size: 1rem; font-weight: bold; margin-bottom: 10px; padding-left: 5px; border-left: 4px solid #555; }
        .history-row { display: flex; align-items: baseline; padding: 8px 5px; border-bottom: 1px solid #262626; transition: background 0.2s; }
        .history-row:hover { background-color: #262626; }
        .hist-time { flex: 0 0 110px; color: #777; font-family: 'Consolas', monospace; font-size: 0.85rem; }
        .hist-txt { flex: 1; color: #ccc; font-size: 0.9rem; line-height: 1.4; }
        .hist-src { font-size: 0.7rem; color: #555; margin-right: 6px; background: #111; padding: 1px 4px; border-radius: 3px; }
        
        /* 统计栏 */
        .stats-box { background: #111; border: 1px solid #333; padding: 10px; border-radius: 6px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
        .stats-label { color: #666; font-size: 0.85rem; }
        .stats-val { color: #f1c40f; font-weight: bold; font-family: monospace; font-size: 1rem; }
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
        st.success(f"✅ AI 就绪")
    else:
        api_key = None
        st.error("❌ 无密钥")
    
    st.divider()
    # 默认分析 15 条
    ai_limit = st.slider("🤖 AI 分析条数", 10, 60, 15)
    
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

# --- 3. AI 分析函数 ---
def analyze_deep_prediction(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
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

# --- 4. 强力时间清洗 ---
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
            s = int(parts[2]) if len(parts) > 2 else 0
            
            # 关键：判断跨日
            dt = now.replace(hour=h, minute=m, second=s)
            # 如果构造出的时间比现在晚超过30分钟，说明肯定是昨天的消息
            # 例如：现在是早上9点，新闻时间是23点，那肯定是昨天的
            if dt > now + datetime.timedelta(minutes=30): 
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. 完整时间 "2024-12-25 ..."
        if "-" in t_str and ":" in t_str:
            return t_str
            
        return str(now)
    except:
        return str(now)

# --- 5. 多源并发抓取 (火力全开) ---

def fetch_sina():
    # 新浪全球 7x24，通常量比较大
    try:
        df = ak.stock_info_global_sina()
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
        return data
    except: return []

def fetch_em():
    # 东方财富，这次我不设 head 限制，有多少拿多少
    try:
        df = ak.stock_news_em(symbol="全部")
        # 东方财富可能返回非常多，我们只取前 500 条防止卡死，但比之前的 200 条多
        df = df.head(500)
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
        return data
    except: return []

def fetch_cls():
    # 财联社，通常只给最新的 50-100 条
    try:
        df = ak.stock_info_global_cls(symbol="全部")
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
        return data
    except: return []

# 新增源：由于 AkShare 经常变动，我们尝试能不能用到其他源
# 如果富途源可用
def fetch_futu():
    try:
        df = ak.stock_info_global_futu()
        data = []
        for _, r in df.iterrows(): data.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "富途"})
        return data
    except: return []

@st.cache_data(ttl=60)
def get_deep_data(ai_count):
    all_news = []
    # 4线程并发
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f1 = executor.submit(fetch_sina)
        f2 = executor.submit(fetch_em)
        f3 = executor.submit(fetch_cls)
        f4 = executor.submit(fetch_futu) # 尝试富途
        
        all_news.extend(f1.result())
        all_news.extend(f2.result())
        all_news.extend(f3.result())
        all_news.extend(f4.result())
        
    df = pd.DataFrame(all_news)
    if df.empty: return df

    # 清洗
    df['full_time'] = df['t'].apply(clean_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # 截取：这次我们保留最多 800 条，希望能覆盖 12h
    df = df.head(800)
    
    # 格式化显示
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(str(x))>16 else str(x))

    # AI 分析 Top N
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_data'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(analyze_deep_prediction, df_head['txt'].tolist()))
        df_head['ai_data'] = results
    
    return pd.concat([df_head, df_tail])

# --- 6. 渲染卡片 ---
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
            <div style="margin-bottom:6px;">
                <span class="time-badge">{row['show_t']}</span>
                <span class="src-badge">{row['src']}</span>
                {html_tags}
            </div>
            <div class="news-text">{row['txt']}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- 7. 主界面 ---
col_main, col_quote = st.columns([3, 1]) 

with col_main:
    # 进度提示
    with st.spinner("🚀 正在全网挖掘，目标 12 小时数据..."):
        df = get_deep_data(ai_limit)
    
    if not df.empty:
        # 统计时间跨度
        t_start = df['full_time'].iloc[0]
        t_end = df['full_time'].iloc[-1]
        count = len(df)
        
        # 顶部统计栏
        st.markdown(f"""
            <div class="stats-box">
                <div>
                    <span class="stats-label">已挖掘情报:</span>
                    <span class="stats-val">{count}</span>
                    <span class="stats-label"> 条</span>
                </div>
                <div>
                    <span class="stats-label">最新:</span>
                    <span class="stats-val">{t_start[5:16]}</span>
                </div>
                <div>
                    <span class="stats-label">最旧:</span>
                    <span class="stats-val">{t_end[5:16]}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        df_analyzed = df[df['ai_data'].notnull()]
        
        bull_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利好' in x['dir'])]
        bear_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利空' in x['dir'])]
        
        exclude = list(bull_df.index) + list(bear_df.index)
        rest_df = df[~df.index.isin(exclude)]
        
        # 双栏
        c_bull, c_bear = st.columns(2)
        with c_bull:
            st.markdown(f"<div class='header-bull'>🔥 利好 ({len(bull_df)})</div>", unsafe_allow_html=True)
            if not bull_df.empty:
                for _, r in bull_df.iterrows(): render_card(r)
            else: st.info("暂无")
        
        with c_bear:
            st.markdown(f"<div class='header-bear'>🟢 利空 ({len(bear_df)})</div>", unsafe_allow_html=True)
            if not bear_df.empty:
                for _, r in bear_df.iterrows(): render_card(r)
            else: st.info("暂无")
        
        # 历史列表
        st.markdown("<div class='history-container'>", unsafe_allow_html=True)
        st.markdown(f"<div class='history-title'>📜 历史时间线 ({len(rest_df)})</div>", unsafe_allow_html=True)
        
        # 使用滚动框，展示更多历史
        with st.container(height=600):
            for _, row in rest_df.iterrows(): # 展示所有剩余的，不限制100条
                st.markdown(
                    f"""
                    <div class="history-row">
                        <div class="hist-time">{row['show_t']}</div>
                        <div class="hist-txt">
                            <span class="hist-src">{row['src']}</span>
                            {row['txt']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.error("数据源暂无响应，请重试")

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
