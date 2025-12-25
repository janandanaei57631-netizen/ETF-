import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 全球市场天眼", layout="wide")
# 每 3 分钟刷新一次 (给 AI 留足思考时间)
st_autorefresh(interval=180000, key="data_refresh")

# 配置 DeepSeek Key
try:
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
    else:
        client = None
except:
    client = None

# --- 2. AI 全能分析大脑 (无限制版) ---
def analyze_market_impact(content):
    if not client: return "❌ 未配置 Key"
    
    # 核心修改：不再限制 ETF 池，让 AI 自由发挥
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
            max_tokens=80 # 极简输出
        )
        return res.choices[0].message.content
    except:
        return "AI 思考超时"

# --- 3. 超级新闻聚合器 (强制最新在最前) ---
@st.cache_data(ttl=180)
def get_global_news():
    news_list = []
    
    # 源1：财联社 (国内)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(20)
        for _, row in df_cn.iterrows():
            news_list.append({
                "raw_time": str(row['发布时间']), # 用于排序
                "display_time": str(row['发布时间'])[5:], # 显示用的短时间 (去掉年份)
                "content": row['内容'],
                "source": "🇨🇳"
            })
    except:
        pass

    # 源2：金十数据 (全球)
    try:
        df_global = ak.js_news(count=20)
        for _, row in df_global.iterrows():
            news_list.append({
                "raw_time": str(row['time']),
                "display_time": str(row['time'])[5:], 
                "content": row['title'],
                "source": "🌍"
            })
    except:
        pass
    
    df = pd.DataFrame(news_list)
    if not df.empty:
        # 【关键】按时间降序排列 (最新的在最上面)
        df.sort_values(by='raw_time', ascending=False, inplace=True)
        # 去重
        df.drop_duplicates(subset=['content'], inplace=True)
        return df.head(10) # 只取最新的10条
    return pd.DataFrame()

# --- 4. 你的持仓监视 (仅用于右侧看价格) ---
# 你可以在这里填入你关心的，或者你想“看一眼”的任何代码
MY_WATCHLIST = [
    "518880", "512480", "513130", "513050", 
    "159915", "510300", "515790", "512690"
]

# --- 5. 页面布局 ---
st.title("👁️ 全球市场 AI 天眼系统")
st.caption("🔴 红涨绿跌 | 🤖 AI 自动捕捉全市场机会")

col1, col2 = st.columns([2, 1])

# 获取数据
with st.spinner("🛰️ 正在扫描全球即时资讯..."):
    news_df = get_global_news()
    prices_df = ak.fund_etf_spot_em()

# 左栏：全市场 AI 分析
with col1:
    st.subheader("🔥 市场异动机会 (AI 实时推演)")
    if not news_df.empty:
        for i, row in news_df.iterrows():
            # 前 6 条自动分析，后面的只看标题（防卡顿）
            if i < 6:
                with st.container(border=True):
                    st.markdown(f"**{row['source']} {row['display_time']}**")
                    st.write(row['content'])
                    
                    # AI 自动分析
                    result = analyze_market_impact(row['content'])
                    
                    # 智能配色
                    if "利好" in result:
                        st.error(f"🚀 {result}") # 红色背景 (A股利好色)
                    elif "利空" in result:
                        st.success(f"🤢 {result}") # 绿色背景 (A股利空色)
                    else:
                        st.info(f"🤔 {result}") # 蓝色中性
            else:
                st.text(f"{row['display_time']} | {row['content'][:40]}...")
    else:
        st.warning("暂无数据，正在重试...")

# 右栏：行情看板 (A股配色)
with col2:
    st.subheader("📊 核心标的行情")
    
    if '代码' in prices_df.columns:
        # 从全市场行情中，筛选出你的 Watchlist
        my_df = prices_df[prices_df['代码'].isin(MY_WATCHLIST)]
        
        for _, row in my_df.iterrows():
            # 这里的 inverse 让涨变红，跌变绿
            st.metric(
                label=row['名称'], 
                value=row['最新价'], 
                delta=f"{row['涨跌幅']}%",
                delta_color="inverse" 
            )
            st.divider()
