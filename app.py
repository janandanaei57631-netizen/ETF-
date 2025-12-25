import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import html # <--- 新增：专门用来处理乱码的工具

# --- 1. 基础设置 ---
st.set_page_config(page_title="AI 交易员", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=300000, key="refresh_final_v1")

# CSS 样式 (优化了时间的显示)
st.markdown("""
    <style>
        .news-box { border-bottom: 1px solid #333; padding: 14px 0; }
        /* 时间标签：改用亮黄色，加宽，防止被挡住 */
        .time-tag { color: #f1c40f; font-weight: bold; font-family: 'Courier New', monospace; font-size: 1.1rem; margin-right: 10px; min-width: 60px; display: inline-block; }
        .source-tag { background: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; margin-right: 8px; vertical-align: middle; }
        
        /* AI 标签样式 */
        .ai-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.9rem; vertical-align: middle; }
        .tag-bull { background: #3d1a1a; color: #ff4b4b; border: 1px solid #ff4b4b; } 
        .tag-bear { background: #1a3d2b; color: #4ade80; border: 1px solid #4ade80; } 
        .tag-neutral { background: #333; color: #aaa; border: 1px solid #555; }
        
        /* 新闻内容：防止太长 */
        .news-content { margin-top: 8px; color: #ccc; line-height: 1.6; font-size: 0.95rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚙️ 控制台")
    client = None
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
        st.success("✅ AI 引擎已连接")
    else:
        st.error("❌ 密钥缺失")
        
    st.divider()
    new_code = st.text_input("➕ 加自选", placeholder="代码")
    if new_code and new_code not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_code)
        st.rerun()
    
    rem_list = st.multiselect("➖ 删自选", st.session_state.watchlist)
    if st.button("删除"):
        for c in rem_list: st.session_state.watchlist.remove(c)
        st.rerun()
        
    if st.button("🧹 修复显示/刷新"):
        st.cache_data.clear()
        st.rerun()

# --- 3. AI 分析 ---
def analyze_simple(content):
    if not client: return "❌无Key"
    try:
        # 截取前100个字给AI，省流量且防止报错
        safe_content = content[:100]
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"分析新闻：{safe_content}\n只回结论：【利好】xx板块 或 【利空】xx板块。8字以内。"}],
            temperature=0.1,
            max_tokens=50
        )
        return res.choices[0].message.content.strip()
    except:
        return "⚠️分析超时"

# --- 4. 数据获取 ---
@st.cache_data(ttl=180)
def get_news_safe():
    news_list = []
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, row in df_cn.iterrows():
            t = str(row['发布时间'])
            # 兼容不同的时间格式
            if len(t) > 10:
                short_t = t[11:16] # 取 HH:MM
            else:
                short_t = t # 如果时间很短就直接显示
            
            news_list.append({"full_time": t, "display_time": short_t, "content": str(row['内容']), "source": "CN"})
    except: pass
    
    try:
        df_js = ak.js_news(count=20)
        for _, row in df_js.iterrows():
            t = str(row['time'])
            if len(t) > 10:
                short_t = t[11:16]
            else:
                short_t = t
            news_list.append({"full_time": t, "display_time": short_t, "content": str(row['title']), "source": "Global"})
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
    st.subheader("🔥 实时情报")
    news_df = get_news_safe()
    
    if not news_df.empty:
        # 这里的 enumerate 确保序号绝对正确
        for i, (index, row) in enumerate(news_df.iterrows()):
            
            # --- 核心修复：防止 HTML 乱码 ---
            # 使用 html.escape 把新闻里的特殊符号变成安全的字符
            safe_content = html.escape(row['content'])
            
            ai_tag_html = ""
            if i < 6:
                ans = analyze_simple(safe_content)
                safe_ans = html.escape(ans) # AI 的回答也要清洗一下
                
                if "利好" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bull">🚀 {safe_ans}</span>'
                elif "利空" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-bear">🧪 {safe_ans}</span>'
                elif "中性" in ans:
                    ai_tag_html = f'<span class="ai-tag tag-neutral">😐 {safe_ans}</span>'
                else:
                    ai_tag_html = f'<span class="ai-tag tag-neutral">🤖 {safe_ans}</span>'

            # 渲染 HTML (结构优化)
            st.markdown(
                f"""
                <div class="news-box">
                    <div style="display: flex; align-items: center; flex-wrap: wrap;">
                        <span class="time-tag">{row['display_time']}</span>
                        <span class="source-tag">{row['source']}</span>
                        {ai_tag_html}
                    </div>
                    <div class="news-content">{safe_content}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("正在获取最新数据...")

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
                            <div style="font-weight:bold; font-size:1.05rem;">{row['名称']}</div>
                            <div style="font-size:0.8rem; color:#888;">{row['代码']}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:1.2rem; font-weight:bold;">{row['最新价']}</div>
                            <div style="color:{c}; font-weight:bold;">{arrow} {val}%</div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.caption("暂无自选，请在左侧添加")
    except:
        st.caption("行情加载中...")
