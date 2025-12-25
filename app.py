import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 配置你的持仓 (在此修改) ---
MY_HOLDINGS = ['512480', '513130', '159915'] 

# 每 60 秒自动刷新
st_autorefresh(interval=60000, key="data_refresh")
st.set_page_config(page_title="ETF 修复版", layout="wide")

# --- 2. 核心修复：双保险新闻获取 ---
@st.cache_data(ttl=60)
def get_safe_news():
    # 方案 A：尝试新版接口 (财联社)
    try:
        df = ak.stock_info_global_cls(symbol="全部")
        # 统一字段名
        if 'content' not in df.columns and '内容' in df.columns:
            df.rename(columns={'内容': 'content', '标题': 'title', '发布时间': 'publish_at'}, inplace=True)
        return df.head(15)
    except:
        pass # 如果A失败，静默转B
    
    # 方案 B：备用接口 (金十数据)
    try:
        df = ak.js_news(count=20)
        df.rename(columns={'time': 'publish_at', 'content': 'title'}, inplace=True)
        df['content'] = df['title'] # 金十只有一列内容
        return df
    except:
        return pd.DataFrame() # 如果都失败，返回空

# --- 3. 页面逻辑 ---
st.title("✅ ETF 实时作战室 (已修复)")

try:
    # 获取数据
    etf_df = ak.fund_etf_spot_em()
    news_df = get_safe_news()
    
    col1, col2 = st.columns([1, 2])

    # 左侧：持仓
    with col1:
        st.subheader("💰 我的持仓")
        my_df = etf_df[etf_df['代码'].isin(MY_HOLDINGS)]
        if not my_df.empty:
            for _, row in my_df.iterrows():
                color = "red" if row['涨跌幅'] > 0 else "green"
                st.metric(label=row['名称'], value=row['最新价'], delta=f"{row['涨跌幅']}%")
        else:
            st.info("持仓列表为空或代码未匹配")
            
    # 右侧：新闻
    with col2:
        st.subheader("📢 实时市场情报")
        if not news_df.empty:
            for _, row in news_df.iterrows():
                # 关键词高亮
                content = str(row.get('content', ''))
                title = str(row.get('title', ''))
                is_urgent = any(k in content for k in ["半导体", "芯片", "恒生", "加息", "印花税"])
                
                display_title = title if title else content[:30]
                
                with st.expander(f"⏰ {row.get('publish_at', '最新')} - {display_title}", expanded=is_urgent):
                    if is_urgent:
                        st.error("🚨 重点关注！")
                    st.write(content)
        else:
            st.warning("正在连接备用数据源，请稍后刷新...")

except Exception as e:
    st.error(f"系统运行中: {str(e)}")
