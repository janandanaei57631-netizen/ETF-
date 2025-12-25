import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 深度投研系统", layout="wide")
st_autorefresh(interval=60000, key="data_refresh") # 1分钟刷新

# 读取你在 Streamlit 后台填写的 DeepSeek Key
try:
    # 尝试读取密钥
    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    else:
        client = None
except:
    client = None

# --- 2. 你的自选 ETF 池 (AI 会从这里面挑) ---
# 你可以把你不关心的删掉，加上你关心的
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
    "513500": "标普500"
}

# --- 3. AI 核心分析大脑 (调用你充值的额度) ---
def get_ai_analysis(news_content):
    if not client: 
        return "❌ 错误：未检测到 API Key，请检查 Secrets 设置。"
    
    # 这是一个昂贵但强大的指令，会消耗 token
    prompt = f"""
    作为资深交易员，请分析这条新闻对投资市场的影响。
    新闻：{news_content}
    
    请严格按照以下格式回答（不要废话）：
    1. 【核心逻辑】：用一句话讲清楚传导链条（如：降息->美元跌->黄金涨）。
    2. 【操作建议】：利好/利空 哪个具体板块？
    3. 【关联标的】：从这个列表中选出最相关的一只ETF：{list(MY_POOL.keys())} {list(MY_POOL.values())}。如果没有直接相关的，请回答“无”。
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个精通宏观经济和A股ETF的专业分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1 # 0.1 代表极其理智，不胡编乱造
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 思考中断: {str(e)}"

# --- 4. 获取数据的函数 ---
@st.cache_data(ttl=300) # 缓存5分钟，避免太频繁刷新
def get_news():
    try:
        # 尝试抓取
        df = ak.stock_info_global_cls(symbol="全部").head(10)
        # 统一列名，防止报错
        if '内容' in df.columns: 
            df.rename(columns={'内容': 'content', '发布时间': 'publish_at'}, inplace=True)
        return df
    except:
        # 备用方案
        try:
            df = ak.js_news(count=10)
            df.rename(columns={'time': 'publish_at', 'title': 'content'}, inplace=True)
            return df
        except:
            return pd.DataFrame()

@st.cache_data(ttl=30)
def get_prices():
    return ak.fund_etf_spot_em()

# --- 5. 网页界面布局 ---
st.title("🧠 AI 智能操盘手 (DeepSeek 加持版)")

# 检查 Key 是否配置成功
if not client:
    st.error("⚠️ 警告：系统未检测到 API Key，AI 无法工作！请去 Streamlit 后台 Secrets 填入 DEEPSEEK_KEY。")

col1, col2 = st.columns([1.5, 1])

# 加载数据
with st.spinner("正在连接交易所数据..."):
    news_df = get_news()
    prices_df = get_prices()

with col1:
    st.subheader("📢 实时新闻深度解读")
    if not news_df.empty:
        for index, row in news_df.iterrows():
            content = row.get('content', '无内容')
            time_str = row.get('publish_at', '刚刚')
            
            with st.container(border=True):
                # 标题和时间
                st.markdown(f"**⏰ {time_str}**")
                st.write(content)
                
                # --- 这里的按钮就是“开关” ---
                # 只有当你点击时，才会扣费调用 AI，省钱又高效
                btn_label = f"🤖 AI 分析影响 (点击预测)"
                if st.button(btn_label, key=f"btn_{index}"):
                    with st.spinner("AI 正在阅读新闻并构建逻辑链..."):
                        # 这里调用 DeepSeek
                        analysis_result = get_ai_analysis(content)
                        # 显示结果，用蓝色背景框
                        st.info(analysis_result)
    else:
        st.warning("暂无最新新闻，请稍后刷新...")

with col2:
    st.subheader("📊 你的自选池行情")
    
    # 过滤出你的池子
    my_codes = list(MY_POOL.keys())
    # 确保列名匹配
    if '代码' in prices_df.columns:
        my_market_data = prices_df[prices_df['代码'].isin(my_codes)]
        
        for _, row in my_market_data.iterrows():
            name = row['名称']
            code = row['代码']
            price = row['最新价']
            change = row['涨跌幅']
            
            st.metric(label=f"{name}", value=price, delta=f"{change}%")
            st.divider()
    else:
        st.error("行情数据格式异常")
