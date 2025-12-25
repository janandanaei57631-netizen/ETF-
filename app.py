import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 量化预测终端", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_quant_v1")

# CSS 样式 (升级了标签系统)
st.markdown("""
    <style>
        /* 基础容器 */
        .news-container { border-bottom: 1px solid #333; padding: 12px 0; font-family: 'Segoe UI', sans-serif; }
        
        /* 顶部元数据行 */
        .meta-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
        .time-badge { color: #f1c40f; font-weight: bold; font-family: monospace; font-size: 1rem; }
        .src-badge { background: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; }
        
        /* --- 核心预测标签 --- */
        /* 1. 方向标签 */
        .tag-dir-up { background: #4a1818; color: #ff4b4b; border: 1px solid #ff4b4b; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }
        .tag-dir-down { background: #1a3020; color: #4ade80; border: 1px solid #4ade80; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; }
        
        /* 2. 板块标签 (蓝色) */
        .tag-sector { background: #1e2a4a; color: #64b5f6; border: 1px solid #64b5f6; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; }
        
        /* 3. 代码标签 (紫色) */
        .tag-code { background: #2d1e4a; color: #b39ddb; border: 1px solid #b39ddb; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-size: 0.9rem; font-weight: bold; cursor: pointer; }
        
        /* 4. 强度标签 (火焰/骷髅) */
        .tag-impact { font-size: 0.9rem; font-weight: bold; margin-left: 5px; }
        
        /* 正文 */
        .news-text { color: #ccc; font-size: 0.95rem; line-height: 1.5; }
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
        st.success(f"✅ AI 交易员已就位")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
    ai_limit = st.slider("🤖 深度预测条数", 10, 60, 20)
    
    st.divider()
    new_c = st.text_input("➕ 加代码", placeholder="512480")
    if new_c and new_c not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_c)
        st.rerun()
        
    rem_list = st.multiselect("➖ 删代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
    
    if st.button("🔴 强制刷新数据"):
        st.cache_data.clear()
        st.rerun()

# --- 3. 核心：AI 深度预测函数 ---
def analyze_deep_prediction(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # 这是一个极度复杂的 Prompt，要求 AI 输出结构化数据
        prompt = f"""
        你是拥有20年经验的A股游资交易员。分析这条新闻：{content[:150]}
        
        请严格按以下格式输出（不要有任何其他废话）：
        方向|具体板块|最相关龙头股代码|预测强度
        
        规则：
        1. 方向：只能填 "利好" 或 "利空" 或 "中性"
        2. 板块：越细越好，如"光刻机"比"电子"好。
        3. 代码：必须给出一只最相关的A股或ETF代码（如 600519 或 512480），不知道就填 "无"。
        4. 强度：只能填 "暴涨"、"大涨"、"微涨"、"暴跌"、"大跌"、"微跌"、"无影响"。
        
        输出示例：
        利好|黄金板块|600547|大涨
        """
        
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=60
        )
        result_text = res.choices[0].message.content.strip()
        
        # 解析返回的文本 "利好|黄金|600547|大涨"
        parts = result_text.split('|')
        if len(parts) == 4:
            return {
                "dir": parts[0].strip(),
                "sector": parts[1].strip(),
                "code": parts[2].strip(),
                "impact": parts[3].strip()
            }
        return None
    except: return None

# --- 4. 辅助函数 ---
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

# --- 5. 数据获取 (三源合一) ---
@st.cache_data(ttl=60)
def get_quant_data(ai_count):
    news = []
    
    # 1. 新浪 (量大)
    try:
        df_sina = ak.stock_info_global_sina()
        for _, r in df_sina.iterrows():
            news.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
    except: pass

    # 2. 东财 (稳)
    try:
        df_em = ak.stock_news_em(symbol="全部").head(300)
        for _, r in df_em.iterrows():
            news.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
    except: pass

    # 3. 财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(100)
        for _, r in df_cn.iterrows():
            news.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    df['full_time'] = df['t'].apply(clean_date)
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(500)
    
    # 显示时间
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(str(x))>16 else str(x))

    # --- AI 分析 ---
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_data'] = None

    if not df_head.empty:
        # 并发分析
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 这里的 analyze_deep_prediction 返回的是字典
            results = list(executor.map(analyze_deep_prediction, df_head['txt'].tolist()))
        df_head['ai_data'] = results
    
    return pd.concat([df_head, df_tail])

# --- 6. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    with st.spinner("AI 正在扫描全市场并预测涨跌幅..."):
        df = get_quant_data(ai_limit)

    if not df.empty:
        st.markdown(f"""
            <div style="background:#111; padding:10px; border-radius:5px; border-left:4px solid #ff4b4b; margin-bottom:15px;">
                <span style="font-size:1.1rem; font-weight:bold; color:#fff;">🚀 AI 市场异动预测</span><br>
                <span style="color:#888;">已深度分析前 {ai_limit} 条重磅情报，生成具体交易信号。</span>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container(height=850):
            for i, row in df.iterrows():
                with st.container(border=True):
                    ai = row['ai_data']
                    
                    # 生成 HTML 标签
                    html_tags = ""
                    
                    if ai:
                        # 1. 方向标签
                        if "利好" in ai['dir']:
                            html_tags += f"<span class='tag-dir-up'>🚀 {ai['dir']}</span> "
                        elif "利空" in ai['dir']:
                            html_tags += f"<span class='tag-dir-down'>🧪 {ai['dir']}</span> "
                        else:
                            html_tags += f"<span class='neutral'>😐 {ai['dir']}</span> "
                        
                        # 2. 板块标签
                        if ai['sector'] and ai['sector'] != "无":
                            html_tags += f"<span class='tag-sector'>📂 {ai['sector']}</span> "
                        
                        # 3. 代码标签 (点击没法直接跳转，但可以复制)
                        if ai['code'] and ai['code'] != "无":
                            html_tags += f"<span class='tag-code'>{ai['code']}</span> "
                            
                        # 4. 强度标签 (视觉冲击力)
                        imp = ai['impact']
                        imp_color = "#ccc"
                        if "暴涨" in imp or "大涨" in imp: imp_color = "#ff4b4b"
                        elif "暴跌" in imp or "大跌" in imp: imp_color = "#4ade80"
                        
                        if imp != "无影响":
                            html_tags += f"<span class='tag-impact' style='color:{imp_color}'>⚡ {imp}</span>"

                    else:
                        html_tags = "<span class='history-tag'>📜 历史/无信号</span>"

                    # 渲染
                    st.markdown(
                        f"""
                        <div class="meta-row">
                            <span class="time-badge">{row['show_t']}</span>
                            <span class="src-badge">{row['src']}</span>
                            {html_tags}
                        </div>
                        <div class="news-text">{row['txt']}</div>
                        """, 
                        unsafe_allow_html=True
                    )
    else:
        st.error("数据加载失败")

with col2:
    st.subheader("📊 核心持仓监控")
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
