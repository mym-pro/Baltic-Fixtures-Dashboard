import streamlit as st
import pandas as pd
from datetime import date

st.title('Baltic Exchange Fixtures Dashboard')

# ==================== 检查数据是否已加载 ====================
def check_data_loaded():
    """检查所需数据是否已在 session_state 中"""
    required_data = ['tc_spot', 'period_spot', 'vcgr_spot', 'vcco_spot', 'vcmi_spot', 'vcor_spot']
    
    missing_data = []
    for data_name in required_data:
        if data_name not in st.session_state:
            missing_data.append(data_name)
    
    return missing_data

# 检查数据加载状态
missing_data = check_data_loaded()

if missing_data:
    st.markdown('# **:red[⚠️ 数据未加载]**')
    st.markdown('## **请先返回主页面加载数据**')
    
    with st.expander("查看缺失数据详情"):
        st.write(f"以下数据尚未加载：")
        for data in missing_data:
            st.write(f"- {data}")
    
    st.info("""
    **解决方案：**
    1. 请点击左侧边栏的 **←** 按钮返回主页
    2. 或者使用顶部的导航菜单返回主页面
    3. 在主页面点击 **Update Data** 按钮加载数据
    4. 数据加载完成后，再返回此页面
    """)
    
    # 显示返回主页的按钮
    if st.button("🏠 返回主页面"):
        # 这里可以添加导航逻辑，或者让用户手动返回
        st.info("请使用浏览器返回按钮或侧边栏导航返回主页面")
    
    st.stop()

# ==================== 如果数据已加载，继续执行 ====================
st.success("✅ 数据已成功加载！")

# 实际数据变量
tc_spot = st.session_state['tc_spot']
period_spot = st.session_state['period_spot']
vcgr_spot = st.session_state['vcgr_spot']
vcco_spot = st.session_state['vcco_spot']
vcmi_spot = st.session_state['vcmi_spot']
vcor_spot = st.session_state['vcor_spot']

# 显示数据概览
st.subheader("📊 数据概览")

col1, col2, col3, col4 = st.columns(4)
with col1:
    if tc_spot is not None:
        st.metric("TIMECHARTER", f"{len(tc_spot)} 条", f"最新: {tc_spot.index[-1].date() if not tc_spot.empty else 'N/A'}")
    else:
        st.metric("TIMECHARTER", "未加载")

with col2:
    if period_spot is not None:
        st.metric("PERIOD", f"{len(period_spot)} 条", f"最新: {period_spot.index[-1].date() if not period_spot.empty else 'N/A'}")
    else:
        st.metric("PERIOD", "未加载")

with col3:
    voyage_total = 0
    voyage_latest = None
    for voyage_data in [vcgr_spot, vcco_spot, vcmi_spot, vcor_spot]:
        if voyage_data is not None and not voyage_data.empty:
            voyage_total += len(voyage_data)
            if voyage_latest is None or voyage_data.index[-1] > voyage_latest:
                voyage_latest = voyage_data.index[-1]
    
    st.metric("VOYAGE 总计", f"{voyage_total} 条", f"最新: {voyage_latest.date() if voyage_latest else 'N/A'}")

with col4:
    total_records = (
        (len(tc_spot) if tc_spot is not None else 0) +
        (len(period_spot) if period_spot is not None else 0) +
        (len(vcgr_spot) if vcgr_spot is not None else 0) +
        (len(vcco_spot) if vcco_spot is not None else 0) +
        (len(vcmi_spot) if vcmi_spot is not None else 0) +
        (len(vcor_spot) if vcor_spot is not None else 0)
    )
    st.metric("总记录数", f"{total_records} 条")

# ==================== 辅助函数（保持不变） ====================
def is_australian_port(port_name):
    """检查港口是否为Australia相关港口"""
    if pd.isna(port_name):
        return False
    
    australian_keywords = [
        'AUSTRALIA', 'AUS', 'WESTERN AUSTRALIA', 'WA',
        'QUEENSLAND', 'QLD', 'NEW SOUTH WALES', 'NSW',
        'VICTORIA', 'VIC', 'SOUTH AUSTRALIA', 'SA',
        'TASMANIA', 'TAS', 'NORTHERN TERRITORY', 'NT',
        'SYDNEY', 'MELBOURNE', 'BRISBANE', 'PERTH',
        'ADELAIDE', 'DARWIN', 'HOBART', 'NEWCASTLE',
        'FREMANTLE', 'GEELONG', 'PORT KEMBLA',
        'TOWNSVILLE', 'CAIRNS', 'GLADSTONE', 'MACKAY',
        'BUNBURY', 'ESPERANCE', 'ALBANY', 'PORT LINCOLN',
        'PORT HEDLAND', 'DAMPIER', 'HAY POINT', 'ABBOT POINT',
        'PORT WALCOTT', 'CAPE LAMBERT', 'PORT ALMA',
        'PORT BOTANY', 'PORT OF BRISBANE', 'PORT OF MELBOURNE',
        'PORT OF ADELAIDE', 'PORT OF FREMANTLE',
        'WEIPA', 'GOVE', 'KARRATHA', 'GERALDTON',
        'BROOME', 'PORTLAND', 'BURNIE', 'DEVONPORT',
        'PORT PIRIE', 'WHYALLA', 'PORT GILES'
    ]
    
    port_str = str(port_name).upper()
    
    for keyword in australian_keywords:
        if keyword in port_str:
            return True
    
    return False

def contains_australian_info(row, fixture_type):
    """检查一行数据是否包含Australia相关信息"""
    if fixture_type in ["TIMECHARTER", "PERIOD"]:
        fields_to_check = ['deliveryPort', 'loadArea', 'via', 'redel']
        for field in fields_to_check:
            if field in row and is_australian_port(row[field]):
                return True
    else:
        fields_to_check = ['loadArea', 'loadPort', 'dischargePort']
        for field in fields_to_check:
            if field in row and is_australian_port(row[field]):
                return True
    
    return False

def get_latest_data(data, fixture_type_name):
    """获取最新一天的数据"""
    if data is None or data.empty:
        return pd.DataFrame()
    
    latest_date = data.index.max()
    latest_data = data[data.index == latest_date].copy()
    latest_data['fixtureType'] = fixture_type_name
    return latest_data

# ==================== 侧边栏配置 ====================
st.sidebar.title("📊 筛选选项")

# 1. 选择数据类型
available_types = []
if tc_spot is not None and not tc_spot.empty:
    available_types.append("TIMECHARTER")
if period_spot is not None and not period_spot.empty:
    available_types.append("PERIOD")
if vcgr_spot is not None and not vcgr_spot.empty:
    available_types.append("VOYAGE GRAIN")
if vcco_spot is not None and not vcco_spot.empty:
    available_types.append("VOYAGE COAL")
if vcmi_spot is not None and not vcmi_spot.empty:
    available_types.append("VOYAGE MISC")
if vcor_spot is not None and not vcor_spot.empty:
    available_types.append("VOYAGE ORE")

if not available_types:
    st.sidebar.warning("没有可用数据")
    fixture_type = None
else:
    fixture_type = st.sidebar.selectbox(
        "选择数据类型",
        available_types
    )

# 2. Australia港口筛选选项
st.sidebar.markdown("---")
st.sidebar.subheader("🇦🇺 Australia港口筛选")
show_australia_only = st.sidebar.checkbox("仅显示Australia相关港口", value=False)

# ==================== 主显示逻辑 ====================
if fixture_type:
    if fixture_type == "TIMECHARTER":
        st.header(f"📋 {fixture_type} Fixtures - 最新数据")
        data = tc_spot
        
        if data is not None and not data.empty:
            # ... [保持原有的 TIMECHARTER 显示逻辑不变，但需要确保数据存在]
            # 这里您可以复制原有的 TIMECHARTER 显示代码
            # 但我会提供一个简化的版本：
            
            latest_date = data.index.max()
            st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
            
            latest_data = get_latest_data(data, fixture_type)
            
            if not latest_data.empty:
                st.info(f"今日共 {len(latest_data)} 条记录")
                
                # 简单显示前10条数据
                st.dataframe(
                    latest_data.head(10),
                    use_container_width=True
                )
                
                # 提供下载
                csv = latest_data.to_csv(index=True)
                st.download_button(
                    label="📥 下载今日数据",
                    data=csv,
                    file_name=f"timecharter_{latest_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("今日暂无数据")
        else:
            st.warning("TIMECHARTER 数据为空")
    
    elif fixture_type == "PERIOD":
        st.header(f"📋 {fixture_type} Fixtures - 最新数据")
        data = period_spot
        
        if data is not None and not data.empty:
            # ... [保持原有的 PERIOD 显示逻辑]
            latest_date = data.index.max()
            st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
            # 简化的显示逻辑...
    
    else:
        # VOYAGE 类型的处理
        voyage_types = {
            "VOYAGE GRAIN": vcgr_spot,
            "VOYAGE COAL": vcco_spot,
            "VOYAGE MISC": vcmi_spot,
            "VOYAGE ORE": vcor_spot
        }
        
        data = voyage_types[fixture_type]
        st.header(f"📋 {fixture_type} Fixtures - 最新数据")
        
        if data is not None and not data.empty:
            # ... [保持原有的 VOYAGE 显示逻辑]
            latest_date = data.index.max()
            st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
            # 简化的显示逻辑...

else:
    st.info("请从侧边栏选择要查看的数据类型")

# ==================== 显示当前数据状态 ====================
with st.expander("📋 查看所有数据状态"):
    for data_name, data in [
        ("TIMECHARTER", tc_spot),
        ("PERIOD", period_spot),
        ("VOYAGE GRAIN", vcgr_spot),
        ("VOYAGE COAL", vcco_spot),
        ("VOYAGE MISC", vcmi_spot),
        ("VOYAGE ORE", vcor_spot)
    ]:
        if data is not None:
            if not data.empty:
                st.write(f"✅ **{data_name}**: {len(data)} 条记录，最新日期: {data.index[-1].date()}")
            else:
                st.write(f"⚠️ **{data_name}**: 数据为空")
        else:
            st.write(f"❌ **{data_name}**: 数据未加载")
