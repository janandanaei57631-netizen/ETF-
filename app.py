import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 实盘代码匹配", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_real_code_v1")

# CSS 样式
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .news-card { 
            padding: 12px; margin-bottom: 12px; border-radius: 8px; 
            border: 1px solid #333; background-color: #1e1e1e;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .left-badges { display: flex; align-items: center; gap: 8px; }
        
        .time-badge { color: #888; font-family: monospace; font-size: 0.85rem; }
        .src-badge { background: #333; color: #aaa; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; }
        
        /* 真正的实盘代码标签 */
        .real-code-tag { 
            background: #2E7D32; /* 真实存在的绿色/深色背景 */
            color: #fff;
            border: 1px solid #4CAF50; 
            padding: 2px 8px; 
            border-radius: 4px; 
            font-family: 'Consolas', monospace; 
            font-size: 0.95rem;    
            font-weight: bold; 
            letter-spacing: 1px;
            cursor: pointer;
        }
        .sector-tag { background: #1565C0; color: #BBDEFB; border: 1px solid #1E88E5; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        
        .impact-high { color: #ff5252; font-weight: bold; font-size: 0.9rem; margin-left: auto; }
        .impact-low { color: #69f0ae; font-weight: bold; font-size: 0.9rem; margin-left: auto; }
        
        .news-text { color: #e0e0e0; font-size: 0.95rem; line-height: 1.5; }
        
        .col-header-bull { color: #ff5252; border-bottom: 2px solid #ff5252; padding: 10px; text-align: center; font-weight: bold; background: rgba(255, 82, 82, 0.1); border-radius: 5px; margin-bottom: 15px; }
        .col-header-bear { color: #69f0ae; border-bottom: 2px solid #69f0ae; padding: 10px; text-align: center; font-weight: bold; background: rgba(105, 240, 174, 0.1); border-radius: 5px; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["518880", "512480", "513130", "159915", "513050"]

with st.sidebar:
    st.header("⚡ 交易员控制台")
    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 连接成功")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    ai_limit = st.slider("🤖 分析条数", 10, 60, 20)
    
    if st.button("🔴 强制刷新"):
        st.cache_data.clear()
        st.rerun()

# --- 3. 核心：建立真实股票数据库 ---
# 为了防止AI瞎编，我们先把所有A股和主流ETF的名字加载到内存里
@st.cache_data(ttl=3600) # 缓存1小时
def load_stock_db():
    try:
        # 1. 获取所有A股实时行情（包含代码和名称）
        df_stocks = ak.stock_zh_a_spot_em()
        # 只需要 代码 和 名称
        stock_map = dict(zip(df_stocks['名称'], df_stocks['代码']))
        
        # 2. 手动补充热门 ETF 字典 (AI 经常提到板块，但不一定能对应到个股)
        etf_map = {
            "半导体": "512480", "芯片": "512480",
            "光伏": "515790", "新能源": "516160", "电池": "159755",
            "白酒": "512690", "消费": "159928", "食品饮料": "512690",
            "医药": "512010", "医疗": "512170", "中药": "560080",
            "证券": "512880", "券商": "512880",
            "银行": "512800", "保险": "512070",
            "军工": "512660", "国防": "512660",
            "黄金": "518880", "有色": "512400",
            "恒生科技": "513130", "中概互联": "513050",
            "美股": "513100", "纳指": "513100",
            "房地产": "512200", "地产": "512200",
            "游戏": "159869", "传媒": "512980", "AI": "159819"
        }
        
        return stock_map, etf_map
    except:
        return {}, {}

# 加载数据库
REAL_STOCK_MAP, ETF_MAP = load_stock_db()

# --- 4. 智能匹配逻辑 ---
def find_real_code(keyword):
    """
    输入：AI 提取的公司名/板块名 (如 '茅台', '宁德', '半导体')
    输出：真实代码 (如 '600519', '300750', '512480')
    """
    if not keyword or keyword == "无": return None
    
    keyword = keyword.replace("公司", "").replace("股份", "").replace("集团", "").strip()
    
    # 1. 先查 ETF 字典 (精准匹配板块)
    if keyword in ETF_MAP:
        return ETF_MAP[keyword]
    
    # 2. 再查个股全名 (精准匹配)
    if keyword in REAL_STOCK_MAP:
        return REAL_STOCK_MAP[keyword]
    
    # 3. 模糊匹配 (最耗时但最智能)
    # 比如 keyword="贵州茅台"，库里也是"贵州茅台"，直接命中
    # 如果 keyword="茅台"，遍历库里的 keys
    for name, code in REAL_STOCK_MAP.items():
        if keyword in name: 
            return code
            
    return None

# --- 5. AI 分析 ---
def analyze_news(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # Prompt 修改：不再让 AI 猜代码，只让它提取【关键主体名称】
        prompt = f"""
        分析新闻：{content[:150]}
        
        请输出：方向|板块|主体名称|强度
        
        1.方向：利好/利空/中性
        2.板块：如"光伏"、"白酒"
        3.主体名称：【最关键】的公司简称或行业名。
           - 不要写代码！
           - 只写中文名，如"贵州茅台"、"中信证券"、"半导体"。
           - 如果没具体公司，就写行业名。
        4.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无
        
        示例：利好|白酒|贵州茅台|大涨
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=60
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) >= 4:
            raw_name = parts[2].strip()
            # 【关键步骤】用 Python 去数据库里查真代码
            real_code = find_real_code(raw_name)
            
            return {
                "dir": parts[0].strip(),
                "sector": parts[1].strip(),
                "name": raw_name,      # AI 提取的名字
                "code": real_code,     # Python 查到的真代码
                "impact": parts[3].strip()
            }
        return None
    except: return None

# --- 6. 数据获取 ---
def clean_date(t_str):
    # 简单清洗时间
    try:
        if len(str(t_str)) > 16: return str(t_str)[5:16]
        return str(t_str)
    except: return ""

@st.cache_data(ttl=60)
def get_data(limit):
    news = []
    # 多源抓取
    try:
        df1 = ak.stock_info_global_sina()
        for _, r in df1.iterrows(): news.append({"t": str(r['时间']), "txt": str(r['内容']), "src": "新浪"})
    except: pass
    
    try:
        df2 = ak.stock_news_em(symbol="全部").head(300)
        for _, r in df2.iterrows(): news.append({"t": str(r['发布时间']), "txt": str(r['新闻标题']), "src": "东财"})
    except: pass

    try:
        df3 = ak.stock_info_global_cls(symbol="全部")
        for _, r in df3.iterrows(): news.append({"t": str(r['发布时间']), "txt": str(r['内容']), "src": "财联"})
    except: pass

    df = pd.DataFrame(news)
    if df.empty: return df
    
    # 排序去重
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(limit + 50) # 多抓一点备用

    # AI 分析
    df_head = df.head(limit).copy()
    df_tail = df.iloc[limit:].copy()
    df_tail['ai'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_news, df_head['txt'].tolist()))
        df_head['ai'] = results
    
    return pd.concat([df_head, df_tail])

# --- 7. 渲染卡片 ---
def render_card(row):
    ai = row['ai']
    tags = ""
    
    if ai:
        # 板块标签
        if ai['sector'] and ai['sector'] != "无":
            tags += f"<span class='sector-tag'>📂 {ai['sector']}</span> "
            
        # --- 核心：代码/名称标签 ---
        if ai['code']:
            # 查到了真代码 -> 显示 代码+名称
            tags += f"<span class='real-code-tag'>✅ {ai['name']} {ai['code']}</span> "
        elif ai['name'] and ai['name'] != "无":
            # 没查到代码 -> 只显示名字 (防止瞎编代码)
            tags += f"<span class='src-badge' style='color:#fff'>{ai['name']}</span> "
            
        # 强度
        imp = ai['impact']
        if "涨" in imp: tags += f"<span class='impact-high'>🔥 {imp}</span>"
        elif "跌" in imp: tags += f"<span class='impact-low'>🟢 {imp}</span>"
    
    st.markdown(
        f"""
        <div class="news-card">
            <div class="header-row">
                <div class="left-badges">
                    <span class="time-badge">{clean_date(row['t'])}</span>
                    <span class="src-badge">{row['src']}</span>
                    {tags}
                </div>
            </div>
            <div class="news-text">{row['txt']}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- 8. 主界面 ---
col1, col2 = st.columns([3, 1])

with col1:
    with st.spinner("🤖 AI 正在阅读新闻并核对 A 股代码库..."):
        df = get_data(ai_limit)
    
    if not df.empty:
        df_ai = df[df['ai'].notnull()]
        
        # 分类
        bull = df_ai[df_ai['ai'].apply(lambda x: x and '利好' in x['dir'])]
        bear = df_ai[df_ai['ai'].apply(lambda x: x and '利空' in x['dir'])]
        
        exclude = list(bull.index) + list(bear.index)
        rest = df[~df.index.isin(exclude)]
        
        c_bull, c_bear = st.columns(2)
        with c_bull:
            st.markdown(f"<div class='col-header-bull'>🔥 红色·利好 ({len(bull)})</div>", unsafe_allow_html=True)
            if not bull.empty:
                for _, r in bull.iterrows(): render_card(r)
            else: st.info("暂无")
            
        with c_bear:
            st.markdown(f"<div class='col-header-bear'>🟢 绿色·利空 ({len(bear)})</div>", unsafe_allow_html=True)
            if not bear.empty:
                for _, r in bear.iterrows(): render_card(r)
            else: st.info("暂无")
            
        st.markdown("---")
        st.caption(f"📜 历史/中性资讯 ({len(rest)})")
        with st.container(height=400):
            for _, r in rest.iterrows():
                st.text(f"{clean_date(r['t'])} | {r['txt']}")
    else:
        st.error("暂无数据，请检查网络或点击刷新")

with col2:
    st.subheader("📊 核心持仓")
    try:
        codes = st.session_state.watchlist
        spot = ak.fund_etf_spot_em()
        my_spot = spot[spot['代码'].isin(codes)]
        for _, r in my_spot.iterrows():
            val = float(r['涨跌幅'])
            c = "red" if val > 0 else "green"
            st.markdown(f"**{r['名称']}** `{r['代码']}` : <span style='color:{c}'>{val}%</span>", unsafe_allow_html=True)
            st.divider()
    except: st.caption("行情连接中...")
