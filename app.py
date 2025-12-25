import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 极简 UI 配置 (CSS 注入) ---
st.set_page_config(page_title="AI 极简天眼", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="data_refresh") # 5分钟刷新

# 强制注入 CSS 修改排版 (变小、变紧凑)
st.markdown("""
    <style>
        /* 缩小顶部空白 */
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        /* 缩小标题字体 */
        h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 1.1rem !important; margin-bottom: 0px !important; }
        /* 缩小卡片间距 */
        div[data-testid="stExpander"] div[role="button"] p { font-size: 0.9rem; }
        /* 紧凑的新闻框 */
        .news-box { border-bottom: 1px solid #333; padding: 8px 0; font-size: 0.9rem; }
        .time-tag { font-weight: bold; color: #ffab40; font-family: monospace; }
        .source-tag { background-color: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 5px; }
        /* 行情数字变小一点 */
        div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 状态管理 (让网页记住你的持仓) ---
# 初始化默认持仓 (如果第一次打开)
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

# --- 3. 侧边栏：管理持仓 & 配置 ---
with st.sidebar:
    st.header("⚙️ 个人配置")
    
    # 添加新标的
    new_code = st.text_input("输入代码添加 (如 512480)", placeholder="输入代码回车")
    if new_code:
        if new_code not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_code)
            st.success(f"已添加 {new_code}")
    
    # 删除旧标的
    st.write("---")
    st.write("🗑️ **管理/删除标的**")
    codes_to_remove = st.multiselect("选择要删除的代码", st.session_state.watchlist)
    if st.button("执行删除"):
        for c in codes_to_remove:
            if c in st.session_state.watchlist:
                st.session_state.watchlist.remove(c)
        st.rerun()

    # 显示 Key 状态
    if "DEEPSEEK_KEY" in st.secrets:
        st.success("✅ AI 密钥已连接")
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
    else:
        st.error("❌ 未配置 DEEPSEEK_KEY")
        client = None

# --- 4. 极简版 AI 分析 ---
def analyze_simple(content):
    if not client: return ""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content}\n请判断：利好什么？利空什么？(只回结论，10个字以内，格式：利好xx / 利空xx)"}],
            temperature=0.1,
            max_tokens=30
        )
        return res.choices[0].message.content
    except:
        return ""

# --- 5. 数据获取 (已修复排序) ---
@st.cache_data(ttl=180)
def get_news():
    news_list = []
    try:
        # 财联社
        df_cn = ak.stock_info_global_cls(symbol="全部").head(15)
        for _, row in df_cn.iterrows():
            t_str = str(row['发布时间'])
            # 提取 HH:MM
            time_short = t_str[11:16] if len(t_str) > 16 else t_str
            news_list.append({"time": time_short, "full_time": t_str, "content": row['内容'], "source": "CN"})
    except: pass
    
    try:
        # 金十
        df_js = ak.js_news(count=15)
        for _, row in df_js.iterrows():
            t_str = str(row['time'])
            time_short = t_str[11:16] if len(t_str) > 16 else t_str
            news_list.append({"time": time_short, "full_time": t_str, "content": row['title'], "source": "Global"})
    except: pass

    df = pd.DataFrame(news_list)
    if not df.empty:
        df.sort_values(by='full_time', ascending=False, inplace=True)
        df.drop_duplicates(subset=['content'], inplace=True)
        return df.head(12) # 看更多条
    return pd.DataFrame()

# --- 6. 极简主界面 ---
col_news, col_price = st.columns([2.5, 1])

with col_news:
    st.subheader("🔥 实时情报 (极简模式)")
    news_df = get_news()
    if not news_df.empty:
        for i, row in news_df.iterrows():
            # 极简排版：一行显示
            # 格式：[10:30] [CN] 新闻内容...  [AI结论]
            
            # 自动 AI 分析前 3 条最重磅的
            ai_tag = ""
            if i < 3: 
                ai_res = analyze_simple(row['content'])
                if "利好" in ai_res:
                    ai_tag = f" <span style='color:#ff4b4b; background:#ffebeb; padding:2px 4px; border-radius:4px; font-size:0.8rem'>🚀 {ai_res}</span>"
                elif "利空" in ai_res:
                    ai_tag = f" <span style='color:#09ab3b; background:#e6f9ed; padding:2px 4px; border-radius:4px; font-size:0.8rem'>🧪 {ai_res}</span>"

            # 使用 HTML 渲染实现极致紧凑
            st.markdown(
                f"""
                <div class="news-box">
                    <span class="time-tag">{row['time']}</span> 
                    <span class="source-tag">{row['source']}</span>
                    {row['content']}
                    {ai_tag}
                </div>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.info("数据加载中...")

with col_price:
    st.subheader("📊 核心标的")
    # 获取动态持仓
    my_codes = st.session_state.watchlist
    
    try:
        df = ak.fund_etf_spot_em()
        my_df = df[df['代码'].isin(my_codes)]
        
        if not my_df.empty:
            # 紧凑列表展示
            for _, row in my_df.iterrows():
                # 计算颜色
                val = float(row['涨跌幅'])
                color = "#ff4b4b" if val > 0 else "#09ab3b" # 红涨绿跌
                arrow = "🔺" if val > 0 else "🟢"
                
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid #eee; padding-bottom:4px;">
                        <div>
                            <div style="font-weight:bold; font-size:0.95rem;">{row['名称']}</div>
                            <div style="color:#888; font-size:0.8rem;">{row['代码']}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-weight:bold; font-size:1.1rem;">{row['最新价']}</div>
                            <div style="color:{color}; font-size:0.9rem;">{arrow} {val}%</div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.caption("暂无数据，请在左侧添加代码")
    except:
        st.error("行情接口连接中...")
