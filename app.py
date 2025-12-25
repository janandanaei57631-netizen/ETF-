import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 全自动投研 (红涨绿跌)", layout="wide")
# 自动刷新频率设为 3 分钟 (180000毫秒)，因为全自动分析比较耗时，刷太快会看不完
st_autorefresh(interval=180000, key="data_refresh")

# 配置 DeepSeek Key
try:
    if "DEEPSEEK_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
    else:
        client = None
except:
    client = None

# --- 2. 你的自选 ETF 池 ---
MY_POOL = {
    "518880": "黄金ETF",
    "512480": "半导体ETF",
    "513130": "恒生科技",
    "513050": "中概互联",
    "159915": "创业板",
    "510300": "沪深300",
    "515790": "光伏ETF",
    "512690": "酒ETF",
    "512010": "医药ETF",
    "513500": "标普500",
    "513330": "恒生互联网"
}

# --- 3. AI 分析大脑 (极简输出版) ---
def analyze_news_automatically(content):
    if not client: return "❌ 未配置 Key"
    
    prompt = f"""
    分析新闻：{content}
    请从以下ETF池中：{list(MY_POOL.keys())} {list(MY_POOL.values())}，选出受影响最大的1个。
    
    格式要求（严禁废话）：
    【方向】利好/利空/中性
    【标的】代码 (名称)
    【逻辑】15字以内短句
    """
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100 # 限制输出长度，提高速度
        )
        return res.choices[0].message.content
    except:
        return "AI 分析超时"

# --- 4. 超级新闻聚合器 (国内+国外) ---
@st.cache_data(ttl=180) # 3分钟缓存
def get_merged_news():
    news_list = []
    
    # 源1：财联社 (国内A股为主)
    try:
        df_cn = ak.stock_info_global_cls(symbol="全部").head(15)
        # 统一格式
        for _, row in df_cn.iterrows():
            # 财联社的时间通常是不带日期的，需要处理一下或者直接用
            news_list.append({
                "time": str(row['发布时间']), 
                "content": row['内容'],
                "source": "🇨🇳 国内"
            })
    except:
        pass

    # 源2：金十数据 (国际/宏观/黄金/美股)
    try:
        df_global = ak.js_news(count=15)
        for _, row in df_global.iterrows():
            news_list.append({
                "time": str(row['time']), 
                "content": row['title'], # 金十的内容在title字段
                "source": "🌍 全球"
            })
    except:
        pass
    
    # 转为 DataFrame 并按时间排序 (简单的字符串排序，要求格式大概一致)
    final_df = pd.DataFrame(news_list)
    if not final_df.empty:
        # 简单去重
        final_df.drop_duplicates(subset=['content'], inplace=True)
        # 取前 10 条显示
        return final_df.head(10)
    return pd.DataFrame()

# --- 5. 页面布局 ---
st.title("🤖 AI 全自动盯盘系统")
st.caption("🔴 红色=涨 | 🟢 绿色=跌 | AI 自动解读前 8 条最新情报")

col1, col2 = st.columns([2, 1])

# 加载数据
with st.spinner("正在聚合全球新闻并进行 AI 分析..."):
    news_df = get_merged_news()
    prices_df = ak.fund_etf_spot_em()

with col1:
    st.subheader("🔥 全球实时情报 (自动分析)")
    if not news_df.empty:
        # 遍历新闻
        for i, row in news_df.iterrows():
            # 只自动分析前 8 条，避免页面卡死
            if i < 8: 
                with st.container(border=True):
                    # 第一行：来源 + 时间
                    st.markdown(f"**{row['source']} | ⏰ {row['time']}**")
                    st.write(row['content'])
                    
                    # --- AI 自动介入 (无需点击) ---
                    ai_result = analyze_news_automatically(row['content'])
                    
                    # 根据利好/利空 改变背景色
                    if "利好" in ai_result:
                        st.success(f"🤖 {ai_result}") # 绿色/浅红背景
                    elif "利空" in ai_result:
                        st.error(f"🤖 {ai_result}")   # 红色/浅红背景
                    else:
                        st.info(f"🤖 {ai_result}")    # 蓝色背景
            else:
                # 超过8条的只显示标题，为了性能
                st.caption(f"{row['time']} - {row['content'][:30]}...")
    else:
        st.warning("暂无数据，请检查网络或刷新")

with col2:
    st.subheader("📊 实时行情 (红涨绿跌)")
    
    my_codes = list(MY_POOL.keys())
    if '代码' in prices_df.columns:
        my_df = prices_df[prices_df['代码'].isin(my_codes)]
        
        for _, row in my_df.iterrows():
            # --- 颜色修正逻辑 ---
            # Streamlit 的 "inverse" 模式下：正数(涨)变红，负数(跌)变绿。
            # 这正是 A 股股民需要的。
            st.metric(
                label=f"{row['名称']}", 
                value=row['最新价'], 
                delta=f"{row['涨跌幅']}%",
                delta_color="inverse" # 关键设置：红涨绿跌
            )
            st.divider()
