import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 基础设置 ---
st.set_page_config(page_title="AI 最终版", layout="wide", initial_sidebar_state="expanded")
# 改了 key，强制让之前的缓存失效
st_autorefresh(interval=300000, key="refresh_v3")

# CSS 美化 (红绿标签)
st.markdown("""
    <style>
        .news-box { border-bottom: 1px solid #333; padding: 12px 0; }
        .time-tag { color: #ffab40; font-weight: bold; font-family: monospace; font-size: 1rem; margin-right: 8px; }
        .source-tag { background: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 8px; }
        
        /* AI 标签 - 强制显示 */
        .ai-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85rem; margin-bottom: 5px; }
        .tag-bull { background: #3d1a1a; color: #ff4b4b; border: 1px solid #ff4b4b; } 
        .tag-bear { background: #1a3d2b; color: #4ade80; border: 1px solid #4ade80; } 
        .tag-neutral { background: #333; color: #aaa; border: 1px solid #555; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏配置 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚙️ 控制台")
    # AI 状态检测
    client = None
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
        st.success("✅ AI 引擎已连接")
    else:
        st.error("❌ 密钥缺失，请检查 Secrets")
        
    st.divider()
    # 标的管理
    new_code = st.text_input("➕ 加自选", placeholder="代码")
    if new_code and new_code not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_code)
        st.rerun()
    
    rem_list = st.multiselect("➖ 删自选", st.session_state.watchlist)
    if st.button("删除"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
        
    # 【新增】手动清除缓存按钮
    if st.button("🧹 强制刷新数据"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析函数 ---
def analyze_simple(content):
    if not client: return "❌无Key"
    try:
        # 简单直接的指令
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{content}\n请只回答结论：是【利好】还是【利空】？对象是谁？\n格式：【利好】xx板块 或 【利空】xx板块\n字数限制：8个字以内。"}],
            temperature=0.1,
            max_tokens=50
        )
        return res.choices[0].message.content.strip()
    except:
        return "⚠️分析超时"

# --- 4. 数据获取 ---
# 改了函数名，防止读取旧缓存
@st.cache_data(ttl=180)
def get_news_v3():
    news_list = []
    try:
        # 财联社
        df_cn = ak.stock_info_global_cls(symbol="全部").head(15)
        for _, row in df_cn.iterrows():
            t = str(row['发布时间'])
            news_list.append({"full_time": t, "display_time": t[11:16], "content": row['内容'], "source": "CN"})
    except: pass
    
    try:
        # 金十
        df_js = ak.js_news(count=15)
        for _, row in df_js.iterrows():
            t = str(row['time'])
            news_list.append({"full_time": t, "display_time": t[11:16], "content": row['title'], "source": "Global"})
    except: pass

    df = pd.DataFrame(news_list)
    if not df.empty:
        df.sort_values(by='full_time', ascending=False, inplace=True)
        df.drop_duplicates(subset=['content'], inplace=True)
        return df.head(15)
    return pd.DataFrame()

# --- 5. 主界面 ---
col1, col2 = st.columns([2.5, 1])

with col1:
    st.subheader("🔥 实时情报 (AI 标签版)")
    news_df = get_news_v3()
    
    if not news_df.empty:
        # 【核心修复】使用 enumerate 强制生成序号 i，从 0 开始
        # 这样无论数据怎么乱，i 永远是 0, 1, 2...
        for i, (index, row) in enumerate(news_df.iterrows()):
            
            ai_tag_html = ""
            
            # 只分析最新的 6 条
            if i < 6:
                ans = analyze_simple(row['content'])
                
                # 标签配色逻辑
                if "利好" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bull">🚀 {ans}</span>'
                elif "利空" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bear">🧪 {ans}</span>'
                elif "中性" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-neutral">😐 {ans}</span>'
                else:
                    # 哪怕出错也要显示出来
                    ai_tag_html = f'<span class="ai-tag tag-neutral">🤖 {ans}</span>'

            st.markdown(
                f"""
                <div class="news-box">
                    <div>
                        <span class="time-tag">{row['display_time']}</span>
                        <span class="source-tag">{row['source']}</span>
                        {ai_tag_html}
                    </div>
                    <div style="margin-top:6px; color:#ccc; line-height:1.4;">{row['content']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("正在加载数据...")

with col2:
    st.subheader("📊 核心标的")
    try:
        my_codes = st.session_state.watchlist
        df = ak.fund_etf_spot_em()
        my_df = df[df['代码'].isin(my_codes)]
        if not my_df.empty:
            for _, row in my_df.iterrows():
                val = float(row['涨跌幅'])
                c = "#ff4b4b" if val > 0 else "#4ade80"
                arrow = "🔺" if val > 0 else "🟢"
                st.markdown(
                    f"""
                    <div style="border-bottom:1px solid #333; padding:10px 0; display:flex; justify-content:space-between;">
                        <div>
                            <div style="font-weight:bold;">{row['名称']}</div>
                            <div style="font-size:0.8rem; color:#888;">{row['代码']}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:1.1rem; font-weight:bold;">{row['最新价']}</div>
                            <div style="color:{c};">{arrow} {val}%</div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.caption("暂无自选")
    except:
        st.caption("行情连接中...")
