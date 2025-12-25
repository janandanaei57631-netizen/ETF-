import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 多空博弈终端", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_split_battle_v1")

# CSS 样式 (优化了分栏显示)
st.markdown("""
    <style>
        /* 全局卡片样式 */
        .news-card { 
            padding: 10px; 
            margin-bottom: 10px; 
            border-radius: 6px; 
            border: 1px solid #333;
            background-color: #1a1a1a;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        /* 顶部元数据 */
        .meta-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
        .time-badge { color: #f1c40f; font-family: monospace; font-weight: bold; font-size: 0.85rem; }
        .src-badge { background: #333; color: #999; padding: 1px 4px; border-radius: 3px; font-size: 0.7rem; border: 1px solid #444; }

        /* --- 标签系统 --- */
        /* 板块 */
        .tag-sector { background: #182236; color: #64b5f6; border: 1px solid #2d4675; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; }
        /* 代码 */
        .tag-code { background: #221836; color: #b39ddb; border: 1px solid #45306b; padding: 1px 5px; border-radius: 3px; font-family: monospace; font-size: 0.8rem; font-weight: bold; }
        
        /* 强度标签 */
        .tag-impact { font-size: 0.8rem; font-weight: bold; margin-left: 4px; }
        
        /* 新闻正文 */
        .news-text { color: #ccc; font-size: 0.9rem; line-height: 1.45; }

        /* --- 分栏标题装饰 --- */
        .header-bull { 
            color: #ff4b4b; 
            border-bottom: 2px solid #ff4b4b; 
            padding-bottom: 8px; 
            margin-bottom: 15px; 
            font-size: 1.1rem; 
            font-weight: bold; 
            text-align: center;
            background: rgba(255, 75, 75, 0.1);
            border-radius: 4px;
        }
        .header-bear { 
            color: #4ade80; 
            border-bottom: 2px solid #4ade80; 
            padding-bottom: 8px; 
            margin-bottom: 15px; 
            font-size: 1.1rem; 
            font-weight: bold; 
            text-align: center;
            background: rgba(74, 222, 128, 0.1);
            border-radius: 4px;
        }
        .header-neutral { 
            color: #888; 
            border-top: 1px solid #333; 
            padding-top: 15px; 
            margin-top: 20px; 
            font-size: 1rem; 
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 量化控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"Server Time: {now.strftime('%H:%M:%S')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    # 建议设为 30，太多会慢
    ai_limit = st.slider("🤖 分析条数", 10, 60, 30)
    
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
        # 极度精简的Prompt，提高响应速度和准确率
        prompt = f"""
        分析新闻：{content[:150]}
        请输出：方向|板块|龙头代码|强度
        1.方向：利好/利空/中性
        2.板块：如"光刻机"，越细越好
        3.代码：最相关A股代码(如600519)，无则填"无"
        4.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无影响
        示例：利好|黄金|600547|大涨
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=60
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) == 4:
            return {"dir": parts[0].strip(), "sector": parts[1].strip(), "code": parts[2].strip(), "impact": parts[3].strip()}
        return None
    except: return None

# --- 4. 数据处理函数 ---
def clean_date(t_str):
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    try:
        # 处理只有时间的情况
        if len(t_str) <= 8:
            parts = t_str.split(":")
            dt = now.replace(hour=int(parts[0]), minute=int(parts[1]), second=0)
            if dt > now + datetime.timedelta(minutes=30): dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return t_str
    except: return str(now)

@st.cache_data(ttl=60)
def get_quant_data(ai_count):
    news = []
    # 1. 新浪
    try:
        df_sina = ak.stock_info_global_sina()
        for _, r in df_sina.iterrows(): news.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
    except: pass
    # 2. 东财
    try:
        df_em = ak.stock_news_em(symbol="全部").head(300)
        for _, r in df_em.iterrows(): news.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
    except: pass
    # 3. 财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows(): news.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    df['full_time'] = df['t'].apply(clean_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(500) # 历史回溯
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(str(x))>16 else str(x))

    # AI 分析 Top N
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_data'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_deep_prediction, df_head['txt'].tolist()))
        df_head['ai_data'] = results
    
    return pd.concat([df_head, df_tail])

# --- 渲染卡片辅助函数 ---
def render_card(row):
    ai = row['ai_data']
    html_tags = ""
    
    if ai:
        # 板块
        if ai['sector'] and ai['sector'] != "无":
            html_tags += f"<span class='tag-sector'>📂 {ai['sector']}</span> "
        # 代码
        if ai['code'] and ai['code'] != "无":
            html_tags += f"<span class='tag-code'>{ai['code']}</span> "
        # 强度
        imp = ai['impact']
        imp_c = "#ccc"
        if "暴涨" in imp or "大涨" in imp: imp_c = "#ff4b4b"
        elif "暴跌" in imp or "大跌" in imp: imp_c = "#4ade80"
        
        # 只显示有强度的
        if imp != "无影响":
            html_tags += f"<span class='tag-impact' style='color:{imp_c}'>⚡ {imp}</span>"
    
    st.markdown(
        f"""
        <div class="news-card">
            <div class="meta-row">
                <span class="time-badge">{row['show_t']}</span>
                <span class="src-badge">{row['src']}</span>
                {html_tags}
            </div>
            <div class="news-text">{row['txt']}</div>
        </div>
        """, 
        unsafe_allow_html=True
    )

# --- 5. 主界面布局 ---
col_main, col_quote = st.columns([3, 1]) 

with col_main:
    with st.spinner("AI 正在扫描全网数据并进行多空分类..."):
        df = get_quant_data(ai_limit)
    
    if not df.empty:
        # 1. 提取 AI 分析过的数据
        df_analyzed = df[df['ai_data'].notnull()]
        
        # 2. 分类：利好(Bull) vs 利空(Bear)
        # 容错：防止 AI 返回 None 导致报错
        bull_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利好' in x['dir'])]
        bear_df = df_analyzed[df_analyzed['ai_data'].apply(lambda x: x is not None and '利空' in x['dir'])]
        
        # 3. 剩下的（中性 或 历史未分析的）
        # 逻辑：总表里 剔除掉 利好和利空 的行
        exclude_indices = list(bull_df.index) + list(bear_df.index)
        rest_df = df[~df.index.isin(exclude_indices)]
        
        # --- 双栏布局 ---
        c_bull, c_bear = st.columns(2)
        
        with c_bull:
            st.markdown(f"<div class='header-bull'>🔥 红色·利好 ({len(bull_df)})</div>", unsafe_allow_html=True)
            if not bull_df.empty:
                for _, row in bull_df.iterrows():
                    render_card(row)
            else:
                st.caption("暂无重大利好")
                
        with c_bear:
            st.markdown(f"<div class='header-bear'>🟢 绿色·利空 ({len(bear_df)})</div>", unsafe_allow_html=True)
            if not bear_df.empty:
                for _, row in bear_df.iterrows():
                    render_card(row)
            else:
                st.caption("暂无重大利空")
        
        # --- 底部通栏：历史消息/中性 ---
        st.markdown(f"<div class='header-neutral'>😐 历史资讯 / 中性消息</div>", unsafe_allow_html=True)
        # 用滚动容器装历史消息，避免太长
        with st.container(height=500):
            for _, row in rest_df.head(100).iterrows(): 
                # 简单显示
                st.markdown(
                    f"""
                    <div style="border-bottom:1px solid #222; padding:6px 0; font-size:0.9rem; color:#888;">
                        <span style="color:#666; font-family:monospace; margin-right:10px;">{row['show_t']}</span>
                        {row['txt']}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    else:
        st.error("数据连接失败")

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
    except:
        st.caption("行情加载中...")
