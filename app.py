import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 极简 UI 配置 ---
st.set_page_config(page_title="AI 极简天眼 (终极修复)", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="data_refresh")

# CSS 样式注入 (红绿标签美化)
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .news-box { border-bottom: 1px solid #333; padding: 12px 0; }
        .time-tag { color: #ffab40; font-weight: bold; font-family: monospace; font-size: 1.1rem; margin-right: 10px; }
        .source-tag { background: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 10px; }
        
        /* AI 标签样式 */
        .ai-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.9rem; margin-bottom: 4px; }
        .tag-bull { background: #3d1a1a; color: #ff4b4b; border: 1px solid #ff4b4b; } /* 利好-红 */
        .tag-bear { background: #1a3d2b; color: #4ade80; border: 1px solid #4ade80; } /* 利空-绿 */
        .tag-neutral { background: #333; color: #aaa; border: 1px solid #555; } /* 中性-灰 */
    </style>
""", unsafe_allow_html=True)

# --- 2. 状态管理 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

# --- 3. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 控制台")
    new_code = st.text_input("➕ 添加代码", placeholder="如 512480")
    if new_code and new_code not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_code)
        st.success(f"已添加 {new_code}")
    
    st.write("---")
    rem_list = st.multiselect("➖ 删除代码", st.session_state.watchlist)
    if st.button("删除选中"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()

    # 检查 Key
    client = None
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
        st.success("✅ AI 连接成功")
    else:
        st.error("❌ 缺少 Key")

# --- 4. AI 分析函数 ---
def analyze_simple(content):
    if not client: return "❌无Key"
    try:
        # 强制 AI 选边站
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content}\n请直接回答：利好谁？利空谁？还是中性？\n格式必须包含关键词：【利好】或【利空】或【中性】。\n例子：【利好】黄金板块\n字数限制：10字以内。"}],
            temperature=0.1,
            max_tokens=60
        )
        return res.choices[0].message.content.strip()
    except:
        return "⚠️分析超时"

# --- 5. 数据获取 (核心修复点！) ---
@st.cache_data(ttl=180)
def get_news():
    news_list = []
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, row in df_cn.iterrows():
            t = str(row['发布时间'])
            news_list.append({"full_time": t, "display_time": t[11:16], "content": row['内容'], "source": "CN"})
    except: pass
    
    try:
        df_js = ak.js_news(count=20)
        for _, row in df_js.iterrows():
            t = str(row['time'])
            news_list.append({"full_time": t, "display_time": t[11:16], "content": row['title'], "source": "Global"})
    except: pass

    df = pd.DataFrame(news_list)
    if not df.empty:
        # 1. 按时间倒序
        df.sort_values(by='full_time', ascending=False, inplace=True)
        # 2. 去重
        df.drop_duplicates(subset=['content'], inplace=True)
        # 3. 【关键修复】重置索引！让第一条变成 0 号，这样循环才能选中它！
        df.reset_index(drop=True, inplace=True)
        return df.head(15)
    return pd.DataFrame()

# --- 6. 页面主逻辑 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    st.subheader("🔥 实时情报 (AI 标签版)")
    news_df = get_news()
    
    if not news_df.empty:
        # 使用 reset_index 后，i 必定是 0, 1, 2...
        for i, row in news_df.iterrows():
            
            # 默认标签为空
            ai_tag_html = ""
            
            # 只分析前 6 条
            if i < 6:
                ans = analyze_simple(row['content'])
                
                # 根据关键词匹配颜色
                if "利好" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bull">🚀 {ans}</span>'
                elif "利空" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bear">🧪 {ans}</span>'
                elif "中性" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-neutral">😐 {ans}</span>'
                else:
                    # 兜底显示
                    ai_tag_html = f'<span class="ai-tag tag-neutral">🤖 {ans}</span>'

            st.markdown(
                f"""
                <div class="news-box">
                    <div>
                        <span class="time-tag">{row['display_time']}</span>
                        <span class="source-tag">{row['source']}</span>
                        {ai_tag_html}
                    </div>
                    <div style="margin-top:8px; color:#ddd; line-height:1.5;">{row['content']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("数据源正在连接，请稍等...")

with col2:
    st.subheader("📊 核心标的")
    my_codes = st.session_state.watchlist
    try:
        df = ak.fund_etf_spot_em()
        my_df = df[df['代码'].isin(my_codes)]
        if not my_df.empty:
            for _, row in my_df.iterrows():
                val = float(row['涨跌幅'])
                c = "#ff4b4b" if val > 0 else "#4ade80" # 红涨绿跌
                arrow
