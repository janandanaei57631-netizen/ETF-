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
# 更换 Key 强制刷新缓存，确保回滚成功
st_autorefresh(interval=60000, key="refresh_rollback_final_v5")

# CSS 样式
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        
        /* 卡片样式 */
        .news-card { 
            padding: 10px; margin-bottom: 8px; border-radius: 6px; 
            border: 1px solid #333; background-color: #1e1e1e;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
        .left-badges { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        
        .time-badge { color: #888; font-family: monospace; font-size: 0.8rem; }
        .src-badge { background: #333; color: #aaa; padding: 1px 4px; border-radius: 3px; font-size: 0.75rem; }
        
        /* 紫色 ETF 标签 (核心) */
        .etf-tag { 
            background: #4a148c; color: #e1bee7; border: 1px solid #7b1fa2; 
            padding: 1px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; 
            font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 4px;
        }
        
        /* 蓝色 概念标签 (备用) */
        .sector-tag { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; padding: 1px 5px; border-radius: 4px; font-size: 0.75rem; }
        
        /* 强度标签 */
        .impact-high { color: #ff5252; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        .impact-low { color: #69f0ae; font-weight: bold; margin-left: auto; font-size: 0.85rem; }
        
        .news-text { color: #ccc; font-size: 0.9rem; line-height: 1.45; }
        
        /* 分栏标题 */
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

# --- 3. 核心：ETF 暴力映射字典 ---
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
    "船": ("510880", "红利ETF"), "运": ("510880", "红利ETF"),

    # === 大消费/医药 ===
    "酒": ("512690", "酒ETF"), "食": ("512690", "酒ETF"), "饮": ("512690", "酒ETF"), "乳": ("512690", "酒ETF"),
    "药": ("512010", "医药ETF"), "医": ("512170", "医疗ETF"), "疫苗": ("512010", "医药ETF"), "中药": ("560080", "中药ETF"),
    "猪": ("516760", "养殖ETF"), "鸡": ("516760", "养殖ETF"), "农": ("516760", "养殖ETF"),

    # === 金融/地产 ===
    "券": ("512880", "证券ETF"), "证": ("512880", "证券ETF
