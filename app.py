import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 深海捕捞", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_deep_sea_v1")

# CSS 样式
st.markdown("""
    <style>
        .bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 6px; border-radius: 4px; border: 1px solid #ff6b6b; font-size: 0.85rem; font-weight: bold; }
        .bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 6px; border-radius: 4px; border: 1px solid #4ade80; font-size: 0.85rem; font-weight: bold; }
        .neutral { background-color: #333; color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .history-tag { background-color: #222; color: #666; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #444; }
        .info-box { background-color: #262730; padding: 10px; border-radius: 5px; border-left: 5px solid #f1c40f; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 控制台")
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    st.caption(f"当前: {now.strftime('%m-%d %H:%M')}")

    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    st.divider()
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
    
    if st.button("🔴 强制深挖数据"):
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

# --- 4. 智能日期补全 (核心) ---
def clean_and_fix_date(t_str):
    """将各种乱七八糟的时间格式统一为 YYYY-MM-DD HH:MM:SS"""
    t_str = str(t_str).strip()
    tz_cn = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(tz_cn)
    
    try:
        # 情况1: 只有时间 "14:30:00" 或 "14:30"
        if len(t_str) <= 8: 
            # 补全日期
            parts = t_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            
            dt = now.replace(hour=h, minute=m, second=s)
            # 如果时间比现在晚太多（比如现在9点，新闻是23点），说明是昨天的
            if dt > now + datetime.timedelta(minutes=30):
                dt = dt - datetime.timedelta(days=1)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 情况2: 只有月日 "12-25 14:30"
        elif len(t_str) < 15 and "-" in t_str:
            return f"{now.year}-{t_str}" + (":00" if t_str.count(":")==1 else "")
            
        # 情况3: 完整时间
        return t_str
    except:
        return t_str # 如果实在解析不了，就原样返回，防止报错

# --- 5. 数据获取 (更换了更强的接口) ---
@st.cache_data(ttl=60)
def get_deep_data(ai_count):
    news = []
    
    # 源1: 财联社电报 (stock_telegraph_cls) - 往往比 global_cls 数据更深
    try:
        df_cn = ak.stock_telegraph_cls(symbol="全部")
        # 尝试取前 300 条
        df_cn = df_cn.head(300)
        for _, r in df_cn.iterrows():
            news.append({"t_raw": str(r['发布时间']), "txt": str(r['内容']), "src": "CN"})
    except: pass

    # 源2: 金十数据 (尝试抓 500 条)
    try:
        df_js = ak.js_news(count=500) 
        for _, r in df_js.iterrows():
            news.append({"t_raw": str(r['time']), "txt": str(r['title']), "src": "Global"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df

    # 1. 修复时间
    df['full_time'] = df['t_raw'].apply(clean_and_fix_date)
    
    # 2. 排序
    df.sort_values(by='full_time', ascending=False, inplace=True)
    df.drop_duplicates(subset=['txt'], inplace=True)
    
    # 3. 限制显示数量，防止浏览器崩溃 (保留400条)
    df = df.head(400)
    
    # 4. 格式化用于显示的时间 (MM-DD HH:MM)
    df['show_t'] = df['full_time'].apply(lambda x: x[5:16] if len(x) > 16 else x)

    # 5. AI 分析
    df_head = df.head(ai_count).copy()
    df_tail = df.iloc[ai_count:].copy()
    df_tail['ai_result'] = "" 

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(analyze_single_news, df_head['txt'].tolist()))
    df_head['ai_result'] = results
    
    final_df = pd.concat([df_head, df_tail])
    return final_df

# --- 6. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    with st.spinner(f"正在深海挖掘历史数据..."):
        df = get_deep_data(ai_limit)
    
    if not df.empty:
        # 计算时间跨度
        start_t = df['full_time'].iloc[-1]
        end_t = df['full_time'].iloc[0]
        total_h = 0
        try:
            t1 = datetime.datetime.strptime(start_t, "%Y-%m-%d %H:%M:%S")
            t2 = datetime.datetime.strptime(end_t, "%Y-%m-%d %H:%M:%S")
            diff = t2 - t1
            total_h = round(diff.total_seconds() / 3600, 1)
        except: pass
        
        # 状态栏 (诚实显示数据范围)
        st.markdown(f"""
            <div class="info-box">
                <b>📊 数据挖掘报告</b><br>
                抓取总量：{len(df)} 条<br>
                最早时间：{start_t} <br>
                最新时间：{end_t} <br>
                <b>⏱️ 实际覆盖时长：{total_h} 小时</b> <br>
                <span style="font-size:0.8rem; color:#888;">(注：如果覆盖不足24h，说明数据源接口已达上限)</span>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container(height=800):
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
        st.error("数据源未返回数据，请稍后重试。")

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
