import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI ETF 狙击手", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_etf_sniper_v1")

# CSS 样式 (配色优化：ETF 专属紫色标签)
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .news-card { 
            padding: 10px; margin-bottom: 8px; border-radius: 6px; 
            border: 1px solid #333; background-color: #1e1e1e;
        }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
        .left-badges { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        
        .time-badge { color: #888; font-family: monospace; font-size: 0.8rem; }
        .src-badge { background: #333; color: #aaa; padding: 1px 4px; border-radius: 3px; font-size: 0.75rem; }
        
        /* ETF 专属标签样式 */
        .etf-tag { 
            background: #4a148c; color: #e1bee7; border: 1px solid #7b1fa2; 
            padding: 1px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; 
            font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 4px;
        }
        
        .sector-tag { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; padding: 1px 5px; border-radius: 4px; font-size: 0.75rem; }
        
        .impact-high { color: #ff5252; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        .impact-low { color: #69f0ae; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        
        .news-text { color: #ccc; font-size: 0.9rem; line-height: 1.45; }
        
        .col-header-bull { color: #ff5252; border-bottom: 2px solid #ff5252; padding: 8px; text-align: center; font-weight: bold; background: rgba(255, 82, 82, 0.1); border-radius: 4px; margin-bottom: 10px; }
        .col-header-bear { color: #69f0ae; border-bottom: 2px solid #69f0ae; padding: 8px; text-align: center; font-weight: bold; background: rgba(105, 240, 174, 0.1); border-radius: 4px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
# 默认自选股改成 ETF
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["512480", "512690", "512880", "513130", "513050", "159915"]

with st.sidebar:
    st.header("⚡ ETF 交易台")
    if "DEEPSEEK_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_KEY"]
        st.success(f"✅ AI 引擎在线")
    else:
        api_key = None
        st.error("❌ 密钥缺失")
    
    ai_limit = st.slider("🤖 分析条数", 10, 60, 20)
    
    if st.button("🔴 强制刷新"):
        st.cache_data.clear()
        st.rerun()

# --- 3. 核心：万物映射 ETF 字典 ---
# 这是一个庞大的映射表，把个股和概念都映射到 ETF
ETF_MAPPING = {
    # --- 科技/半导体 ---
    "半导体": "512480", "芯片": "512480", "中芯国际": "512480", "北方华创": "512480", "海光信息": "512480", "寒武纪": "512480",
    "人工智能": "159819", "AI": "159819", "算力": "159819", "CPO": "159819", "科大讯飞": "159819", "三六零": "159819",
    "计算机": "512720", "软件": "512720", "信创": "512720", "金山办公": "512720",
    "游戏": "159869", "传媒": "512980", "神州泰岳": "159869", "昆仑万维": "512980",
    "消费电子": "159732", "立讯精密": "159732", "歌尔": "159732",

    # --- 新能源/车 ---
    "新能源": "516160", "光伏": "515790", "隆基": "515790", "通威": "515790", "阳光电源": "515790",
    "电池": "159755", "锂电": "159755", "宁德时代": "159755", "宁德": "159755", "亿纬锂能": "159755",
    "汽车": "516110", "比亚迪": "516110", "长安汽车": "516110", "赛力斯": "516110",

    # --- 消费/医药 ---
    "白酒": "512690", "食品": "512690", "消费": "159928", "贵州茅台": "512690", "茅台": "512690", "五粮液": "512690", "泸州老窖": "512690",
    "医药": "512010", "医疗": "512170", "CXO": "512170", "恒瑞医药": "512010", "药明康德": "512170", "迈瑞医疗": "512170",
    "中药": "560080", "片仔癀": "560080",

    # --- 金融/地产 ---
    "证券": "512880", "券商": "512880", "中信证券": "512880", "东方财富": "512880", "光大证券": "512880",
    "银行": "512800", "招商银行": "512800", "工商银行": "512800",
    "保险": "512070", "中国平安": "512070",
    "房地产": "512200", "地产": "512200", "万科": "512200", "保利": "512200",

    # --- 跨境/宽基/资源 ---
    "美股": "513100", "纳指": "513100", "英伟达": "513100", "特斯拉": "513100", "苹果": "513100", "微软": "513100",
    "港股": "513130", "恒生科技": "513130", "腾讯": "513130", "阿里巴巴": "513130", "美团": "513130", "快手": "513130",
    "中概": "513050", "拼多多": "513050",
    "黄金": "518880", "紫金矿业": "518880", "有色": "512400", "铜": "512400",
    "沪深300": "510300", "科创50": "588000", "创业板": "159915"
}

def map_to_etf(keyword):
    """
    输入：新闻主体（如'茅台'）
    输出：ETF代码和名称（如 '512690'）
    """
    if not keyword or keyword == "无": return None
    
    # 1. 直接匹配
    if keyword in ETF_MAPPING: return ETF_MAPPING[keyword]
    
    # 2. 模糊匹配 (比如 AI 提取了 '贵州茅台酒', 字典里有 '贵州茅台')
    for k, v in ETF_MAPPING.items():
        if k in keyword: return v
        if keyword in k: return v # 反向匹配
    
    return None

# --- 4. AI 分析 ---
def analyze_news(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        # Prompt 修改：让 AI 提取“最核心的概念”
        prompt = f"""
        分析新闻：{content[:150]}
        请输出：方向|核心概念|强度
        
        1.方向：利好/利空/中性
        2.核心概念：提取最相关的【行业名】或【龙头公司名】。
          - 尽量用通用词，如"白酒"、"光伏"、"英伟达"、"中信证券"。
          - 不要写代码。
        3.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无
        
        示例：利好|白酒|大涨
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=50
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) >= 3:
            concept = parts[1].strip()
            # 映射到 ETF
            etf_code = map_to_etf(concept)
            
            return {
                "dir": parts[0].strip(),
                "concept": concept,
                "etf": etf_code,
                "impact": parts[2].strip()
            }
        return None
    except: return None

# --- 5. 数据获取 ---
def clean_date(t_str):
    try:
        if len(str(t_str)) > 16: return str(t_str)[5:16]
        return str(t_str)
    except: return ""

@st.cache_data(ttl=60)
def get_data(limit):
    news = []
    # 极速多源
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
    
    df.drop_duplicates(subset=['txt'], inplace=True)
    df = df.head(limit + 50) 

    df_head = df.head(limit).copy()
    df_tail = df.iloc[limit:].copy()
    df_tail['ai'] = None

    if not df_head.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_news, df_head['txt'].tolist()))
        df_head['ai'] = results
    
    return pd.concat([df_head, df_tail])

# --- 6. 渲染卡片 ---
def render_card(row):
    ai = row['ai']
    tags = ""
    
    if ai:
        # 显示 ETF 标签
        if ai['etf']:
            # 显示为：[ETF图标] 概念名 代码
            tags += f"<span class='etf-tag'>📊 {ai['concept']} {ai['etf']}</span> "
        elif ai['concept'] and ai['concept'] != "无":
            # 没匹配到 ETF，显示蓝色概念标签
            tags += f"<span class='sector-tag'>{ai['concept']}</span> "
            
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

# --- 7. 主界面 ---
col1, col2 = st.columns([3, 1])

with col1:
    with st.spinner("🚀 AI 正在将新闻映射到 ETF 策略..."):
        df = get_data(ai_limit)
    
    if not df.empty:
        df_ai = df[df['ai'].notnull()]
        
        bull = df_ai[df_ai['ai'].apply(lambda x: x and '利好' in x['dir'])]
        bear = df_ai[df_ai['ai'].apply(lambda x: x and '利空' in x['dir'])]
        
        exclude = list(bull.index) + list(bear.index)
        rest = df[~df.index.isin(exclude)]
        
        c_bull, c_bear = st.columns(2)
        with c_bull:
            st.markdown(f"<div class='col-header-bull'>🔥 利好 ETF ({len(bull)})</div>", unsafe_allow_html=True)
            if not bull.empty:
                for _, r in bull.iterrows(): render_card(r)
            else: st.info("暂无信号")
            
        with c_bear:
            st.markdown(f"<div class='col-header-bear'>🟢 利空 ETF ({len(bear)})</div>", unsafe_allow_html=True)
            if not bear.empty:
                for _, r in bear.iterrows(): render_card(r)
            else: st.info("暂无信号")
            
        st.markdown("---")
        st.caption(f"📜 市场噪音 ({len(rest)})")
        with st.container(height=400):
            for _, r in rest.iterrows():
                st.text(f"{clean_date(r['t'])} | {r['txt']}")
    else:
        st.error("暂无数据")

with col2:
    st.subheader("📊 自选 ETF")
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
