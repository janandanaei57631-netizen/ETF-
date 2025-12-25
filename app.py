import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 极简 UI 配置 (CSS 注入) ---
st.set_page_config(page_title="AI 极简天眼 (修复版)", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="data_refresh") # 5分钟刷新

# 强制注入 CSS 修改排版
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
        .news-box { border-bottom: 1px solid #333; padding: 10px 0; font-size: 0.95rem; line-height: 1.5; }
        .time-tag { font-weight: bold; color: #ffab40; font-family: monospace; font-size: 1rem; }
        .source-tag { background-color: #444; color: #eee; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin: 0 5px; }
        
        /* --- 核心修复：AI 标签样式 --- */
        .tag-bull { background-color: #5a2d2d; color: #ff6b6b; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; border: 1px solid #ff6b6b; margin-left: 8px; }
        .tag-bear { background-color: #1e3a2a; color: #4ade80; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; border: 1px solid #4ade80; margin-left: 8px; }
        .tag-neutral { background-color: #333; color: #aaa; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-left: 8px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 状态管理 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

# --- 3. 侧边栏：管理持仓 ---
with st.sidebar:
    st.header("⚙️ 个人配置")
    new_code = st.text_input("输入代码添加 (如 512480)", placeholder="输入代码回车")
    if new_code and new_code not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_code)
        st.success(f"已添加 {new_code}")
    
    st.write("---")
    codes_to_remove = st.multiselect("删除标的", st.session_state.watchlist)
    if st.button("执行删除"):
        for c in codes_to_remove:
            if c in st.session_state.watchlist:
                st.session_state.watchlist.remove(c)
        st.rerun()

    # DeepSeek 连接检查
    client = None
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
        st.success("✅ AI 引擎已就绪")
    else:
        st.error("❌ 缺少 DEEPSEEK_KEY")

# --- 4. 修复后的 AI 分析函数 ---
def analyze_simple(content):
    if not client: return "❌ 未连接密钥"
    try:
        # 提示词强化：强制 AI 必须选一个方向，不要含糊其辞
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content}\n请极简回答：是【利好】还是【利空】？对象是谁？\n格式必须是：利好-板块名 或 利空-板块名 或 中性-无影响。不要超过10个字。"}],
            temperature=0.1,
            max_tokens=50
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ 分析超时"

# --- 5. 数据获取 ---
@st.cache_data(ttl=180)
def get_news():
    news_list = []
    try:
        # 财联社
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20) # 抓更多
        for _, row in df_cn.iterrows():
            t_str = str(row['发布时间'])
            time_short = t_str[11:16] if len(t_str) > 16 else t_str
            news_list.append({"time": time_short, "full_time": t_str, "content": row['内容'], "source": "CN"})
    except: pass
    
    try:
        # 金十
        df_js = ak.js_news(count=20)
        for _, row in df_js.iterrows():
            t_str = str(row['time'])
            time_short = t_str[11:16] if len(t_str) > 16 else t_str
            news_list.append({"time": time_short, "full_time": t_str, "content": row['title'], "source": "Global"})
    except: pass

    df = pd.DataFrame(news_list)
    if not df.empty:
        df.sort_values(by='full_time', ascending=False, inplace=True)
        df.drop_duplicates(subset=['content'], inplace=True)
        return df.head(15) 
    return pd.DataFrame()

# --- 6. 极简主界面 ---
col_news, col_price = st.columns([2.5, 1])

with col_news:
    st.subheader("🔥 实时情报 (含 AI 标签)")
    news_df = get_news()
    
    if not news_df.empty:
        # 显示前 6 条的 AI 分析 (增加到6条，确保你能看到效果)
        for i, row in news_df.iterrows():
            ai_html = ""
            
            # 只有前 6 条调用 AI
            if i < 6:
                ai_res = analyze_simple(row['content'])
                
                # --- 标签渲染逻辑 (修复核心) ---
                if "利好" in ai_res:
                    ai_html = f'<span class="tag-bull">🚀 {ai_res}</span>'
                elif "利空" in ai_res:
                    ai_html = f'<span class="tag-bear">🧪 {ai_res}</span>'
                elif "中性" in ai_res:
                    ai_html = f'<span class="tag-neutral">😐 {ai_res}</span>'
                else:
                    # 即使 AI 回答格式不对，也把结果显示出来，防止“消失”
                    ai_html = f'<span class="tag-neutral">🤖 {ai_res}</span>'
            
            # 渲染新闻行
            st.markdown(
                f"""
                <div class="news-box">
                    <span class="time-tag">{row['time']}</span> 
                    <span class="source-tag">{row['source']}</span>
                    {ai_html} <br>
                    <span style="color:#ccc;">{row['content']}</span>
                </div>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.warning("正在加载新闻源...")

with col_price:
    st.subheader("📊 核心标的")
    my_codes = st.session_state.watchlist
    
    try:
        df = ak.fund_etf_spot_em()
        my_df = df[df['代码'].isin(my_codes)]
        
        if not my_df.empty:
            for _, row in my_df.iterrows():
                val = float(row['涨跌幅'])
                color = "#ff4b4b" if val > 0 else "#4ade80" # 红涨绿跌
                arrow = "🔺" if val > 0 else "🟢"
                
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1px solid #333; padding-bottom:6px;">
                        <div>
                            <div style="font-weight:bold; font-size:1rem; color:#fff;">{row['名称']}</div>
                            <div style="color:#888; font-size:0.8rem;">{row['代码']}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-weight:bold; font-size:1.1rem; color:#fff;">{row['最新价']}</div>
                            <div style="color:{color}; font-weight:bold; font-size:0.9rem;">{arrow} {val}%</div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.info("请在左侧添加代码")
    except:
        st.error("行情接口连接中...")
