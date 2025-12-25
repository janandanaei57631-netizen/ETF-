import streamlit as st
import akshare as ak
import traceback

st.set_page_config(page_title="诊断模式")
st.title("🛠️ 正在诊断你的网站...")

st.write("1. 正在尝试连接金融数据源...")

try:
    # 尝试抓取最简单的实时数据
    df = ak.fund_etf_spot_em()
    st.success(f"✅ 成功！抓取到 {len(df)} 条 ETF 行情。")
    st.dataframe(df.head(5))
except Exception:
    st.error("❌ 抓取失败，请把下面的英文错误截图发给我：")
    st.code(traceback.format_exc())

st.write("2. 正在尝试连接新闻源...")
try:
    news = ak.stock_telegraph_cls()
    st.success(f"✅ 成功！抓取到 {len(news)} 条新闻。")
    st.write(news.head(3))
except Exception:
    st.error("❌ 新闻接口报错：")
    st.code(traceback.format_exc())
