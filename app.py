import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 【这里修改你的持仓】 ---
# 请把下面的数字换成你实际买入的 ETF 代码
MY_HOLDINGS = ['512480', '513130', '159915'] 

# 每 60 秒自动刷新一次网页
st_autorefresh(interval=60000, key="data_refresh")

st.set_page_config(page_title="ETF 实时战报", layout="wide")

# AI 配置 (从系统密匙读取)
if "DEEPSEEK_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
else:
    client = None

# 获取数据
@st.cache_data(ttl=30)
def get_data():
    return ak.fund_etf_spot_em(), ak.stock_telegraph_cls()

st.title("📊 ETF 实时情报 & 持仓监控")

try:
    etf_df, news_df = get_data()
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("💰 我的持仓状态")
        my_stocks = etf_df[etf_df['代码'].isin(MY_HOLDINGS)]
        for _, row in my_stocks.iterrows():
            # 涨红跌绿
            delta_val = f"{row['涨跌幅']}%"
            st.metric(label=row['名称'], value=row['最新价'], delta=delta_val)
        st.divider()
        st.write("🔥 市场热门")
        st.dataframe(etf_df[['名称', '最新价', '涨跌幅']].head(10))

    with col2:
        st.subheader("📢 实时新闻 (每分钟自动更新)")
        for _, row in news_df.head(15).iterrows():
            content = row['content']
            # 自动高亮：如果新闻提到你持仓的关键字（简单匹配）
            is_urgent = any(h in content for h in ["半导体", "芯片", "恒生", "港股", "创业板"])
            
            with st.expander(f"{row['publish_at']} - {row['title']}", expanded=is_urgent):
                if is_urgent:
                    st.error("🚨 监测到可能影响你持仓的重要新闻！")
                st.write(content)
                if st.button("AI 解析影响", key=row['title']):
                    if client:
                        res = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": f"简述该新闻对ETF的利好或利空影响：{content}"}]
                        )
                        st.info(res.choices[0].message.content)
                    else:
                        st.warning("请先在 Streamlit 设置中配置 API Key")

except:
    st.error("数据加载中，请稍后刷新...")
