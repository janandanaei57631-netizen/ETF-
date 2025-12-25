import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 全球市场天眼", layout="wide")
# 每 5 分钟刷新 (给 AI 留足时间，也防止太快刷掉结果)
st_autorefresh(interval=300000, key="data_refresh")

# 配置 DeepSeek Key
try:
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
    else:
        client = None
except:
    client = None

# --- 2. AI 全能分析大脑 ---
def analyze_market_impact(content):
    if not client: return "❌ 未配置 Key"
    
    prompt = f"""
    你是华尔街资深交易员。请分析这条新闻对【全球金融市场】的即时影响。
    新闻：{content}
    
    请直接给出结论，不要废话，严格按以下格式：
    【方向】利好 / 利空 / 中性
    【标的】请找出最相关的一个ETF或板块（例如：黄金、恒生科技、半导体、原油、美债等）
    【逻辑】用15个字以内讲清逻辑链
    """
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        return res.choices[0].message.content
    except:
        return "AI 思考超时"

# --- 3. 超级新闻聚合器 (已修复排序BUG) ---
@st.cache_data(ttl=180)
def get_global_news():
    news_list = []
    
    # 源1：财联社
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, row in df_cn.iterrows():
            news_list.append({
                "raw_time": str(row['发布时间']), 
                "display_time": str(row['发布时间'])[5:-3], # 优化时间显示：去头去尾
                "content": row['内容'],
                "source": "🇨🇳"
            })
    except:
        pass

    # 源2：金十数据
    try:
        df_global = ak.js_news(count=20)
        for _, row in df_global.iterrows():
            news_list.append({
                "raw_time": str(row['time']),
                "display_time": str(row['time'])[5:-3], 
                "content": row['title'],
                "source": "🌍"
            })
    except:
        pass
    
    df = pd.DataFrame(news_list)
    if not df.empty:
        # 【关键修复】排序后，必须重置索引，否则 AI 会跳过分析
        df.sort_values(by='raw_time', ascending=False, inplace=True)
        df.drop_duplicates(subset=['content'], inplace=True)
        df.reset_index(drop=True, inplace=True) # <--- 就是这行代码修好了BUG
        return df.head(10)
    return pd.DataFrame()

# --- 4. 核心监视池 ---
MY_WATCHLIST = [
    "518880", "512480", "513130", "513050", 
    "159915", "510300", "515790", "512690"
]

# --- 5. 页面布局 ---
st.title("👁️ 全球市场 AI 天眼系统")
st.caption("🔴 红涨绿跌 | 🤖 AI 自动捕捉全市场机会 | 修复排序显示")

col1, col2 = st.columns([2, 1])

# 获取数据
with st.spinner("🛰️ 正在扫描全球即时资讯..."):
    news_df = get_global_news()
    prices_df = ak.fund_etf_spot_em()

# 左栏：AI 分析
with col1:
    st.subheader("🔥 市场异动机会 (AI 实时推演)")
    if not news_df.empty:
        # 使用 enumerate 确保序号正确
        for i, row in news_df.iterrows():
            # 只有前 5 条最新的新闻，AI 才会自动展开分析（避免等待太久）
            if i < 5:
                with st.container(border=True):
                    st.markdown(f"**{row['source']} {row['display_time']}**")
                    st.write(row['content'])
                    
                    # AI 自动分析
                    result = analyze_market_impact(row['content'])
                    
                    # 智能配色框
                    if "利好" in result:
                        st.error(f"🚀 {result}") # 红色背景
                    elif "利空" in result:
                        st.success(f"🤢 {result}") # 绿色背景
                    else:
                        st.info(f"🤔 {result}") # 蓝色背景
            else:
                # 5条之后的旧新闻，只显示一行字
                st.text(f"{row['display_time']} | {row['content'][:35]}...")
    else:
        st.warning("暂无数据，正在重试...")

# 右栏：行情看板
with col2:
    st.subheader("📊 核心标的行情")
    if '代码' in prices_df.columns:
        my_df = prices_df[prices_df['代码'].isin(MY_WATCHLIST)]
        for _, row in my_df.iterrows():
            st.metric(
                label=row['名称'], 
                value=row['最新价'], 
                delta=f"{row['涨跌幅']}%",
                delta_color="inverse" # 红涨绿跌
            )
            st.divider()
