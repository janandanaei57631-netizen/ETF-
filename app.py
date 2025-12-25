import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI ETF 全覆盖", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_etf_full_v2")

# CSS 样式
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
        
        /* 紫色 ETF 标签 */
        .etf-tag { 
            background: #4a148c; color: #e1bee7; border: 1px solid #7b1fa2; 
            padding: 1px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; 
            font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 4px;
        }
        /* 蓝色 概念标签 (当找不到ETF时显示) */
        .sector-tag { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; padding: 1px 5px; border-radius: 4px; font-size: 0.75rem; }
        
        .impact-high { color: #ff5252; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        .impact-low { color: #69f0ae; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        
        .news-text { color: #ccc; font-size: 0.9rem; line-height: 1.45; }
        
        .col-header-bull { color: #ff5252; border-bottom: 2px solid #ff5252; padding: 8px; text-align: center; font-weight: bold; background: rgba(255, 82, 82, 0.1); border-radius: 4px; margin-bottom: 10px; }
        .col-header-bear { color: #69f0ae; border-bottom: 2px solid #69f0ae; padding: 8px; text-align: center; font-weight: bold; background: rgba(105, 240, 174, 0.1); border-radius: 4px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏 ---
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

# --- 3. 核心：超级 ETF 字典 (大幅扩容) ---
# 逻辑：关键词 -> ETF代码
ETF_MAPPING = {
    # === 热门赛道 ===
    "低空": "512660", "飞行汽车": "512660", "无人机": "512660", "军工": "512660", "国防": "512660", # 低空经济通常映射军工或高端制造
    "机器人": "159770", "机器": "159770", "自动化": "159770",
    "算力": "159819", "CPO": "159819", "光模块": "159819", "服务器": "159819", "AI": "159819",
    "芯片": "512480", "半导体": "512480", "集成电路": "512480", "存储": "512480",
    "光伏": "515790", "太阳能": "515790", "硅料": "515790", "储能": "560580",
    "电池": "159755", "锂电": "159755", "固态电池": "159755", "新能源车": "516160",
    
    # === 周期/资源 ===
    "黄金": "518880", "贵金属": "518880",
    "有色": "512400", "铜": "512400", "铝": "512400", "稀土": "516150",
    "石油": "561360", "油气": "561360", "化工": "516020",
    "煤炭": "515220", "电力": "561560", "绿电": "561560",
    "航运": "510880", "港口": "510880", # 这里的红利ETF包含很多交通运输
    
    # === 大金融/红利 ===
    "证券": "512880", "券商": "512880", "牛市旗手": "512880",
    "银行": "512800", "保险": "512070",
    "红利": "510880", "高股息": "510880", "中字头": "510880", "国企": "510880",
    
    # === 消费/医药 ===
    "白酒": "512690", "食品": "512690", "饮料": "512690",
    "猪肉": "516760", "养殖": "516760", "农业": "516760",
    "医药": "512010", "创新药": "512010", "中药": "560080", "医疗": "512170",
    "家电": "159996", "旅游": "562510",
    
    # === 宽基/海外 ===
    "美股": "513100", "纳指": "513100", "标普": "513500",
    "港股": "513130", "恒生": "513130", "腾讯": "513130",
    "科创": "588000", "创业板": "159915", "中证500": "510500", "沪深300": "510300", "微盘": "512100"
}

def map_to_etf(keyword):
    if not keyword or keyword == "无": return None
    
    # 1. 精准匹配
    if keyword in ETF_MAPPING: return ETF_MAPPING[keyword]
    
    # 2. 模糊包含匹配 (例如 AI 提取了"工业母机"，映射表里没有，但如果 AI 提取了"半导体设备"，能匹配"半导体")
    # 反向遍历：看字典里的 key 是否出现在 keyword 里
    for key, code in ETF_MAPPING.items():
        if key in keyword: 
            return code
            
    return None

# --- 4. AI 分析 ---
def analyze_news(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        # ⚠️ Prompt 升级：要求 AI 往 ETF 赛道上靠
        prompt = f"""
        分析新闻：{content[:150]}
        请输出：方向|核心赛道|强度
        
        1.方向：利好/利空/中性
        2.核心赛道：
           - 必须提取最接近的【ETF板块名】。
           - 比如提到"万丰奥威"，你要提取"低空"或"军工"。
           - 比如提到"中远海控"，你要提取"航运"。
           - 尽量使用通用词：半导体、白酒、证券、游戏、光伏、黄金、红利。
        3.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无
        
        示例：利好|低空|大涨
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=50
        )
        parts = res.choices[0].message.content.strip().split('|')
        if len(parts) >= 3:
            concept = parts[1].strip()
            # 尝试映射
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
            # 命中字典，显示紫色
            tags += f"<span class='etf-tag'>📊 {ai['concept']} {ai['etf']}</span> "
        elif ai['concept'] and ai['concept'] != "无":
            # 没命中字典，显示蓝色，提示用户自己手动查一下
            tags += f"<span class='sector-tag'>📂 {ai['concept']}</span> "
            
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
    with st.spinner("🚀 AI 正在进行 ETF 模糊匹配..."):
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
    except: st.caption("行情加载中...")
