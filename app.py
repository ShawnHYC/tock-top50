import streamlit as st
import pandas as pd
import requests
import twstock
import random
import urllib3

# 關閉 SSL 警告 (為了繞過公司防火牆)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定頁面配置
st.set_page_config(page_title="台股即時漲幅 Top 50 (終極版)", layout="wide")

# CSS 優化
st.markdown("""
<style>
    .stDataFrame {font-size: 1.1rem;}
    .status-ok {color: green; font-weight: bold;}
    .status-err {color: red; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.title("📈 台股盤中漲幅排行榜 Top 50")
st.markdown("數據源策略：**鉅亨網 API** (優先) ➔ **模擬數據** (保底)")

# --- 核心功能函數 ---

def get_industry(stock_id):
    """利用 twstock 庫查詢股票代號對應的產業"""
    try:
        if stock_id in twstock.codes:
            return twstock.codes[stock_id].group
    except:
        pass
    return "其他/未知"

def fetch_cnyes_data():
    """
    嘗試從鉅亨網 API 獲取數據 (Json 格式，無需解析 HTML)
    """
    # 鉅亨網 API 網址 (TSE=上市, OTC=上櫃)
    api_urls = [
        ("上市", "https://api.cnyes.com/media/api/v1/ranking/realtime?limit=50&market=TSE&orderBy=change_percent&sort=desc"),
        ("上櫃", "https://api.cnyes.com/media/api/v1/ranking/realtime?limit=50&market=OTC&orderBy=change_percent&sort=desc")
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.cnyes.com/'
    }

    all_data = []
    
    for market, url in api_urls:
        try:
            # verify=False 是關鍵：繞過公司防火牆 SSL 檢查
            r = requests.get(url, headers=headers, timeout=10, verify=False)
            
            if r.status_code == 200:
                data = r.json()
                # 解析 JSON 結構
                if 'data' in data and 'data' in data['data']:
                    stock_list = data['data']['data']
                    for item in stock_list:
                        # 鉅亨網欄位對應
                        # 0: ?, 1: 代號, 2: 名稱, 6: 股價, 7: 漲跌, 8: 漲跌幅
                        # 注意：不同 API 版本欄位可能不同，這裡嘗試用 key 抓取 (如果是 dict) 
                        # 或用 list index 抓取
                        
                        code = item.get('symbol', '').split('.')[0] # 例如 2330
                        name = item.get('name', '')
                        price = item.get('price', 0)
                        change_rate = item.get('change_percent', 0)
                        
                        if code:
                            all_data.append({
                                "代號": code,
                                "名稱": name,
                                "股價": price,
                                "漲跌幅(%)": float(change_rate),
                                "市場": market
                            })
        except Exception as e:
            print(f"鉅亨網連線失敗 ({market}): {e}")
            continue
            
    return all_data

def generate_mock_data():
    """
    生成模擬數據 (當網路完全被擋時使用)
    """
    mock_data = []
    industries = ['半導體', '航運', '生技醫療', '電子零組件', '光電', '金融']
    names = ['台積電', '長榮', '陽明', '聯電', '鴻海', '國巨', '萬海', '高端', '技嘉', '緯創']
    
    for i in range(50):
        base_name = names[i % len(names)]
        mock_data.append({
            "代號": f"{1101+i}",
            "名稱": f"{base_name}-{i}KY",
            "產業別": industries[i % len(industries)],
            "股價": round(random.uniform(10, 500), 2),
            "漲跌幅(%)": round(random.uniform(0.5, 9.99), 2),
            "市場": "上市" if i % 2 == 0 else "上櫃"
        })
    # 排序
    mock_data.sort(key=lambda x: x['漲跌幅(%)'], reverse=True)
    return mock_data

@st.cache_data(ttl=60)
def get_final_data():
    status_text = st.empty()
    progress = st.progress(0)
    
    # 1. 嘗試真實數據
    status_text.text("正在連線鉅亨網 API (略過 SSL 檢查)...")
    real_data = fetch_cnyes_data()
    progress.progress(50)
    
    if real_data:
        df = pd.DataFrame(real_data)
        # 排序
        df = df.sort_values(by='漲跌幅(%)', ascending=False).head(50)
        
        status_text.text("正在匹配產業資料庫...")
        df['產業別'] = df['代號'].apply(get_industry)
        
        final_df = df[['代號', '名稱', '產業別', '股價', '漲跌幅(%)', '市場']]
        progress.progress(100)
        status_text.empty()
        return final_df, "real"
    
    # 2. 如果失敗，使用模擬數據
    progress.progress(80)
    status_text.text("⚠️ 無法連線，切換至模擬數據模式...")
    mock_data = generate_mock_data()
    df = pd.DataFrame(mock_data)
    
    progress.progress(100)
    status_text.empty()
    return df, "mock"

# --- 介面互動區 ---

col1, col2 = st.columns([1, 4])
with col1:
    if st.button('🔄 立即更新數據', type="primary"):
        get_final_data.clear()
        st.rerun()

# 執行抓取
df, source_type = get_final_data()

with col2:
    if source_type == "real":
        st.markdown('<span class="status-ok">✅ 連線成功：使用鉅亨網即時數據</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-err">⚠️ 連線受阻：目前顯示為「模擬演示數據」 (請檢查網路防火牆)</span>', unsafe_allow_html=True)

if not df.empty:
    with st.expander("📊 查看產業分佈統計", expanded=False):
        industry_counts = df['產業別'].value_counts()
        st.bar_chart(industry_counts)

    st.dataframe(
        df.style.format({"漲跌幅(%)": "{:.2f}%", "股價": "{:.2f}"})
          .applymap(lambda x: 'color: #d63031; font-weight: bold', subset=['漲跌幅(%)']),
        height=800, 
        use_container_width=True,
        hide_index=True
    )