import streamlit as st
import akshare as ak
import pandas as pd
from openai import OpenAI
from streamlit_autorefresh import st_autorefresh
import concurrent.futures
import datetime
import pytz 
import logging

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 智能ETF匹配", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, key="refresh_smart_match_v1")

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
        /* 蓝色 概念标签 */
        .sector-tag { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; padding: 1px 5px; border-radius: 4px; font-size: 0.75rem; }
        /* 调试小字 */
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

# --- 3. 核心：智能同义词库 (双字起步) ---
# 结构：关键词列表 -> (ETF代码, ETF名称)
# 只要 AI 提取的词包含列表里的任意一个词，就匹配成功
SMART_MAPPING = {
    # === 热门科技 ===
    ("低空", "飞行汽车", "无人机", "通航", "eVTOL", "军工", "国防", "航天"): ("512660", "军工龙头"),
    ("机器人", "自动化", "减速器", "人型机器人", "伺服"): ("159770", "机器人ETF"),
    ("AI", "人工智能", "算力", "服务器", "光模块", "CPO", "大模型", "英伟达"): ("159819", "人工智能"),
    ("半导体", "芯片", "集成电路", "晶圆", "光刻机", "存储芯片", "中芯"): ("512480", "半导体ETF"),
    ("信创", "软件", "操作系统", "网络安全", "计算机", "云计算", "大数据"): ("512720", "计算机ETF"),
    ("游戏", "电竞", "网游", "手游"): ("159869", "游戏ETF"),
    ("传媒", "短剧", "影视", "院线", "元宇宙"): ("512980", "传媒ETF"),
    ("消费电子", "苹果产业链", "果链", "智能手机", "华为手机", "立讯"): ("159732", "消电ETF"),
    ("通信", "5G", "6G", "运营商", "中国移动"): ("515880", "通信ETF"),
    
    # === 新能源/高端制造 ===
    ("汽车", "整车", "乘用车", "自动驾驶", "无人驾驶", "智能驾驶"): ("516110", "汽车ETF"),
    ("电池", "锂电", "固态电池", "动力电池", "储能", "宁德时代"): ("159755", "电池ETF"),
    ("光伏", "太阳能", "硅料", "组件", "逆变器", "隆基"): ("515790", "光伏ETF"),
    ("新能源", "新能车", "电动车"): ("516160", "新能源ETF"),

    # === 资源/周期/红利 ===
    ("黄金", "贵金属", "金价"): ("518880", "黄金ETF"),
    ("有色", "铜矿", "铝业", "稀土", "紫金矿业"): ("512400", "有色ETF"),
    ("石油", "原油", "石化", "油气", "三桶油"): ("561360", "石油ETF"),
    ("煤炭", "动力煤", "焦煤", "神华"): ("515220", "煤炭ETF"),
    ("电力", "绿电", "火电", "核电", "电网"): ("561560", "电力ETF"),
    ("红利", "高股息", "中字头", "国企改革", "央企"): ("510880", "红利ETF"),
    ("航运", "海运", "港口", "集运", "中远海控"): ("510880", "红利ETF"), # 归入红利或交运

    # === 消费/医药 ===
    ("白酒", "高端酒", "茅台", "五粮液"): ("512690", "酒ETF"),
    ("食品", "饮料", "乳业", "调味品", "零食"): ("512690", "酒ETF"),
    ("猪肉", "养殖", "生猪", "饲料", "农业"): ("516760", "养殖ETF"),
    ("医药", "创新药", "疫苗", "CXO", "恒瑞"): ("512010", "医药ETF"),
    ("医疗", "医疗器械", "医美", "眼科", "牙科"): ("512170", "医疗ETF"),
    ("中药", "中成药"): ("560080", "中药ETF"),
    ("家电", "白色家电", "空调", "冰箱"): ("159996", "家电ETF"),
    ("旅游", "免税", "酒店", "航空", "机场"): ("562510", "旅游ETF"),

    # === 金融/地产 ===
    ("证券", "券商", "投行", "牛市旗手"): ("512880", "证券ETF"),
    ("银行", "四大行"): ("512800", "银行ETF"),
    ("保险", "寿险", "财险"): ("512070", "保险ETF"),
    ("房地产", "地产", "楼市", "万科", "保利"): ("512200", "地产ETF"),

    # === 宽基/海外 ===
    ("纳指", "纳斯达克", "美股", "标普", "特斯拉", "微软"): ("513100", "纳指ETF"),
    ("港股", "恒生", "港股通", "腾讯", "美团", "阿里"): ("513130", "恒生科技"),
    ("科创板", "科创50"): ("588000", "科创50"),
    ("创业板", "创50"): ("159915", "创业板"),
    ("沪深300", "大盘股"): ("510300", "沪深300"),
    ("中证500", "中盘股"): ("510500", "中证500"),
    ("中证1000", "微盘股"): ("512100", "中证1000")
}

def smart_map_to_etf(ai_keyword):
    """
    智能匹配逻辑 (拒绝单字，最长匹配优先)
    """
    ai_keyword = (ai_keyword or "").strip()
    if not ai_keyword or ai_keyword == "无":
        return None, None
    
    # 扁平化字典，方便处理
    # key_list = [("飞行汽车", "512660", "军工龙头"), ("低空", "512660", "军工龙头")...]
    flat_mapping = []
    for keywords, (code, name) in SMART_MAPPING.items():
        for k in keywords:
            flat_mapping.append((k, code, name))
    
    # 核心算法：按关键词长度降序排列 (最长词优先)
    # 这样 "新能源汽车" 会先于 "汽车" 被匹配
    flat_mapping.sort(key=lambda x: len(x[0]), reverse=True)
    
    for key, code, name in flat_mapping:
        # 1. 过滤掉单字 (双重保险)
        if len(key) < 2: continue
        
        # 2. 包含匹配
        # 如果 字典里的词 (key) 出现在 AI提取的词 (ai_keyword) 里
        if key in ai_keyword:
            return code, name
            
    # 所有正向包含均未命中后，再尝试反向包含，避免“汽车”误中“飞行汽车”
    for key, code, name in flat_mapping:
        if len(ai_keyword) >= 2 and ai_keyword in key:
            return code, name
            
    return None, None

# --- 4. AI 分析 ---
def analyze_news(content):
    if not api_key: return None
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        # Prompt 升级：要求提取具体行业
        prompt = f"""
        分析新闻：{content[:150]}
        请输出：方向|核心赛道|强度
        
        1.方向：利好/利空/中性
        2.核心赛道：
           - 提取最具体的【行业或板块全称】。
           - 不要用单字（不要写"车"，要写"汽车"或"新能源车"）。
           - 不要写代码。
           - 举例：低空经济、光伏组件、白酒、消费电子、人工智能。
        3.强度：暴涨/大涨/微涨/暴跌/大跌/微跌/无
        
        示例：利好|低空经济|大涨
        """
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=50
        )
        raw = res.choices[0].message.content
        if not isinstance(raw, str):
            logging.warning("AI 返回格式异常：正文不是字符串")
            return None
        parts = [part.strip() for part in raw.split("|")]
        if (
            len(parts) != 3
            or not all(parts)
            or parts[0] not in {"利好", "利空", "中性"}
            or parts[2] not in {"暴涨", "大涨", "微涨", "暴跌", "大跌", "微跌", "无"}
        ):
            logging.warning("AI 返回格式异常：应为方向|核心赛道|强度")
            return None
        direction, concept, impact = parts
        code, name = smart_map_to_etf(concept)
        return {
            "dir": direction,
            "concept": concept,
            "etf_code": code,
            "etf_name": name,
            "impact": impact,
        }
    except Exception:
        logging.exception("AI 分析失败")
        return None

# --- 5. 数据获取 ---
def clean_date(t_str):
    try:
        if len(str(t_str)) > 16: return str(t_str)[5:16]
        return str(t_str)
    except: return ""

@st.cache_data(ttl=60)
def get_data_smart(limit):
    news = []
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
        code = ai.get('etf_code')
        name = ai.get('etf_name')
        concept = ai.get('concept', '未知')
        
        if code:
            # 命中字典
            tags += f"<span class='etf-tag'>📊 {name} {code}</span> "
            tags += f"<span class='debug-tag'>[AI:{concept}]</span>"
        elif concept and concept != "无":
            # 未命中
            tags += f"<span class='sector-tag'>📂 {concept}</span> "
            tags += f"<span class='debug-tag'>[未匹配]</span>"
            
        imp = ai.get('impact', '')
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
    with st.spinner("🚀 AI 正在进行智能语义匹配..."):
        df = get_data_smart(ai_limit)
    
    if not df.empty:
        df_ai = df[df['ai'].notnull()]
        
        bull = df_ai[df_ai['ai'].apply(lambda x: x and '利好' in x.get('dir', ''))]
        bear = df_ai[df_ai['ai'].apply(lambda x: x and '利空' in x.get('dir', ''))]
        
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
