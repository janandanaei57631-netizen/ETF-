import streamlit as st
import akshare as ak
import pandas as pd
import traceback
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# 自动刷新
st_autorefresh(interval=60000, key="data_refresh")

st.set_page_config(page_title="ETF 调试模式", layout="wide")

# 配置持仓
MY_HOLDINGS = ['512480', '513130', '159915']

st.title("🛠️ 网站诊断模式")

# --- 第一步：测试行情数据 ---
st.subheader("1. 行情数据测试")
try:
    df = ak.fund_etf_spot_em()
    st.success(f"✅ 成功获取行情，共 {len(df)} 条数据")
    
    # 显示我的持仓
    my_df = df[df['代码'].isin(MY_HOLDINGS)]
    if not my_df.empty:
        st.dataframe(my_df[['代码', '名称', '最新价', '涨跌幅']])
    else:
        st.warning("⚠️ 没有匹配到你的持仓代码，请检查代码是否正确")
        
except Exception as e:
    st.error("❌ 行情获取失败！原因如下：")
    st.code(traceback.format_exc()) 

st.divider()

# --- 第二步：测试新闻数据 ---
st.subheader("2. 新闻数据测试")
try:
    # 尝试另一个更稳定的接口
    news = ak.stock_telegraph_cls()
    st.success(f"✅ 成功获取新闻，共 {len(news)} 条")
    st.dataframe(news.head(5))
except Exception as e:
    st.error("❌ 新闻获取失败！原因如下：")
    st.code(traceback.format_exc())
