import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI ETF 暴力匹配", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_force_match_v3")

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
        .sector-tag { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; padding: 1px 5px; border-radius: 4px; font-size: 0.75rem; }
        
        /* 调试用的小字 */
        .debug-tag { font-size: 0.7rem; color: #555; margin-left: 5px; font-family: monospace; }

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

# --- 3. 核心：超全 ETF 字典 ---
# 这里的 Key 是关键词，Value 是 (ETF代码, ETF简称)
ETF_MAPPING = {
    # === 热门黑科技 ===
    "低空": ("512660", "军工龙头"), "飞行": ("512660", "军工龙头"), "无人机": ("512660", "军工龙头"), "航天": ("512660", "军工龙头"), "卫星": ("512660", "军工龙头"),
    "机器人": ("159770", "机器人ETF"), "机器": ("159770", "机器人ETF"), "自动化": ("159770", "机器人ETF"), "减速器": ("159770", "机器人ETF"),
    "AI": ("159819", "人工智能"), "人工智能": ("159819", "人工智能"), "算力": ("159819", "人工智能"), "服务器": ("159819", "人工智能"), "CPO": ("159819", "人工智能"),
    "芯片": ("512480", "半导体ETF"), "半导体": ("512480", "半导体ETF"), "集成电路": ("512480", "半导体ETF"), "存储": ("512480", "半导体ETF"),
    "信创": ("512720", "计算机ETF"), "软件": ("512720", "计算机ETF"), "操作系统": ("512720", "计算机ETF"), "网络安全": ("512720", "计算机ETF"),
    "游戏": ("159869", "游戏ETF"), "传媒": ("512980", "传媒ETF"), "短剧": ("512980", "传媒ETF"),
    
    # === 新能源/车 ===
    "车": ("516110", "汽车ETF"), "汽车": ("516110", "汽车ETF"), "智驾": ("516110", "汽车ETF"),
    "电池": ("159755", "电池ETF"), "锂": ("159755", "电池ETF"), "固态": ("159755", "电池ETF"), "宁德": ("159755", "电池ETF"),
    "光伏": ("515790", "光伏ETF"), "太阳能": ("515790", "光伏ETF"), "硅": ("515790", "光伏ETF"), "储能": ("560580", "储能ETF"),

    # === 资源/周期 ===
    "金": ("518880", "黄金ETF"), "银": ("518880", "黄金ETF"), 
    "有色": ("512400", "有色ETF"), "铜": ("512400", "有色ETF"), "铝": ("512400", "有色ETF"), "稀土": ("516150", "稀土ETF"),
    "油": ("561360", "石油ETF"), "石化": ("561360", "石油ETF"), "煤": ("515220", "煤炭ETF"),
    "电": ("561560", "电力ETF"), "绿电": ("561560", "电力ETF"), "核电": ("561560", "电力ETF"),
    "船": ("510880", "红利ETF"), "运": ("510880", "红利ETF"), # 航运通常在红利里

    # === 大消费/医药 ===
    "酒": ("512690", "酒ETF"), "食": ("512690", "酒ETF"), "饮": ("512690", "酒ETF"), "乳": ("512690", "酒ETF"),
    "药": ("512010", "医药ETF"), "医": ("512170", "医疗ETF"), "疫苗": ("512010", "医药ETF"), "中药": ("560080", "中药ETF"),
    "猪": ("516760", "养殖ETF"), "鸡": ("516760", "养殖ETF"), "农": ("516760", "养殖ETF"),

    # === 金融/地产 ===
    "券": ("512880", "证券ETF"), "证": ("512880", "证券ETF"),
    "银": ("512800", "银行ETF"), "保": ("512070", "保险ETF"), "险": ("512070", "保险ETF"),
    "房": ("512200", "地产ETF"), "地": ("512200", "地产ETF"),

    # === 宽基/海外 ===
    "美": ("513100", "纳指ETF"), "纳指": ("513100", "纳指ETF"), "英伟达": ("513100", "纳指ETF"), "苹果": ("513100", "纳指ETF"),
    "港": ("513130", "恒生科技"), "恒生": ("513130", "恒生科技"), "腾讯": ("513130", "恒生科技"),
    "科创": ("588000", "科创50"), "创业": ("159915", "创业板"), "中证": ("510500", "中证500")
}

def map_to_etf(keyword):
    """
    暴力匹配逻辑：
    只要 字典里的 Key 出现在了 AI识别词 里，就匹配！
    例如：字典有 "低空"，AI 识别出 "低空经济发展"， "低空" in "低空经济发展" -> 成功！
    """
    if not keyword or keyword == "无": return None
    
    # 1. 直接匹配
    if keyword in ETF_MAPPING: return ETF_MAPPING[keyword]
    
    # 2. 暴力包含匹配
    for key, val in ETF_MAPPING.items():
        # 如果字典里的关键词 (如 "低空") 出现在了 AI识别词 (如 "低空经济") 里
        if key in keyword:
            return val
        # 反之亦然
        if keyword in key:
            return val
            
    return None

# --- 4. AI 分析 ---
def analyze_news(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        prompt = f"""
        分析新闻：{content[:150]}
        请输出：方向|核心词|强度
        
        1.方向：利好/利空/中性
        2.核心词：
           - 提取最核心的【行业关键词】，不要写长句子。
           - 比如提到"万丰奥威"，你要提取"低空"。
           - 比如提到"中远海控"，你要提取"海运"。
           - 尽量用2-3个字，如：半导体、机器人、白酒、黄金。
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
            etf_info = map_to_etf(concept)
            
            etf_code = etf_info[0] if etf_info else None
            etf_name = etf_info[1] if etf_info else None
            
            return {
                "dir": parts[0].strip(),
                "concept": concept, # 这是 AI 提取的原始词
                "etf_code": etf_code,
                "etf_name": etf_name,
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
        if ai['etf_code']:
            # 命中！显示紫色标签
            tags += f"<span class='etf-tag'>📊 {ai['etf_name']} {ai['etf_code']}</span> "
            # 调试：显示AI提取了什么词
            tags += f"<span class='debug-tag'>[AI识别:{ai['concept']}]</span>"
        elif ai['concept'] and ai['concept'] != "无":
            # 未命中，显示蓝色
            tags += f"<span class='sector-tag'>📂 {ai['concept']}</span> "
            tags += f"<span class='debug-tag'>[未匹配]</span>"
            
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
    with st.spinner("🚀 AI 正在进行 ETF 暴力匹配..."):
        df = get_data(ai_limit)
    
    if not df.empty:
        df_ai = df[df['ai'].notnull()]
        
        bull = df_ai[df_ai['ai'].apply(lambda x: x and '利好' in x['dir'])]
        bear = df_ai[df_ai['ai'].apply(lambda x: x and '利空' in x['dir'])]
        
        exclude = list(bull.index) + list(bear.index)
        rest = df[~df.index.isin(exclude)]
        
        c_bull, c_bear = st.columns(2)
        with c_bull:
            st.markdown(f"<div class='col-header-bull'>🔥 利好 ({len(bull)})</div>", unsafe_allow_html=True)
            if not bull.empty:
                for _, r in bull.iterrows(): render_card(r)
            else: st.info("暂无信号")
            
        with c_bear:
            st.markdown(f"<div class='col-header-bear'>🟢 利空 ({len(bear)})</div>", unsafe_allow_html=True)
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
