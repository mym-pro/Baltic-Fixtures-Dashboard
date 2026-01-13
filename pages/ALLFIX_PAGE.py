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
    
    # 如果有任何一个数据不在 session_state 中，返回 False
    if missing_data:
        return False, missing_data
    
    # 检查数据是否有效（不为 None）
    for data_name in required_data:
        if st.session_state[data_name] is None:
            missing_data.append(f"{data_name} (值为 None)")
    
    return len(missing_data) == 0, missing_data

# 检查数据加载状态
data_loaded, missing_data = check_data_loaded()

if not data_loaded:
    st.markdown('# **:red[⚠️ 数据未完全加载]**')
    st.markdown('## **请先返回主页面加载数据**')
    
    with st.expander("查看缺失数据详情"):
        st.write(f"以下数据未加载或为空：")
        for data in missing_data:
            st.write(f"- {data}")
    
    # 显示当前已加载的数据状态
    st.subheader("当前已加载数据状态")
    cols = st.columns(3)
    data_status = {
        'tc_spot': 'TIMECHARTER',
        'period_spot': 'PERIOD',
        'vcgr_spot': 'VOYAGE GRAIN',
        'vcco_spot': 'VOYAGE COAL',
        'vcmi_spot': 'VOYAGE MISC',
        'vcor_spot': 'VOYAGE ORE'
    }
    
    idx = 0
    for data_key, data_name in data_status.items():
        if data_key in st.session_state and st.session_state[data_key] is not None:
            if not st.session_state[data_key].empty:
                cols[idx % 3].success(f"✅ {data_name}: {len(st.session_state[data_key])} 条")
            else:
                cols[idx % 3].warning(f"⚠️ {data_name}: 数据为空")
        else:
            cols[idx % 3].error(f"❌ {data_name}: 未加载")
        idx += 1
    
    st.info("""
    **解决方案：**
    1. 请点击左侧边栏的 **←** 按钮返回主页
    2. 或者使用顶部的导航菜单返回主页面
    3. 在主页面点击 **Update Data** 按钮加载数据
    4. 数据加载完成后，再返回此页面
    
    **注意：** 有些数据源可能暂时没有数据（如 VOYAGE MISC），这是正常的。
    """)
    
    # 显示返回主页的按钮
    if st.button("🏠 返回主页面"):
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

def get_data_info(data, name):
    """获取数据信息"""
    if data is None:
        return f"{name}: 未加载", "未加载", "N/A"
    elif data.empty:
        return f"{name}: 无数据", "0 条", "N/A"
    else:
        latest_date = data.index[-1].date() if not data.empty else 'N/A'
        return f"{name}", f"{len(data)} 条", f"最新: {latest_date}"

with col1:
    name, count, latest = get_data_info(tc_spot, "TIMECHARTER")
    if tc_spot is None:
        st.metric(name, "未加载")
    elif tc_spot.empty:
        st.metric(name, "0 条")
    else:
        st.metric(name, count, latest)

with col2:
    name, count, latest = get_data_info(period_spot, "PERIOD")
    if period_spot is None:
        st.metric(name, "未加载")
    elif period_spot.empty:
        st.metric(name, "0 条")
    else:
        st.metric(name, count, latest)

with col3:
    # 计算VOYAGE类型总数
    voyage_data_list = [vcgr_spot, vcco_spot, vcmi_spot, vcor_spot]
    voyage_total = 0
    voyage_latest = None
    
    for voyage_data in voyage_data_list:
        if voyage_data is not None and not voyage_data.empty:
            voyage_total += len(voyage_data)
            if voyage_latest is None or (not voyage_data.empty and voyage_data.index[-1] > voyage_latest):
                voyage_latest = voyage_data.index[-1]
    
    if voyage_total > 0:
        st.metric("VOYAGE 总计", f"{voyage_total} 条", f"最新: {voyage_latest.date() if voyage_latest else 'N/A'}")
    else:
        st.metric("VOYAGE 总计", "无数据")

with col4:
    # 计算总记录数
    total_records = 0
    for data in [tc_spot, period_spot, vcgr_spot, vcco_spot, vcmi_spot, vcor_spot]:
        if data is not None and not data.empty:
            total_records += len(data)
    
    if total_records > 0:
        st.metric("总记录数", f"{total_records} 条")
    else:
        st.metric("总记录数", "无数据")

# ==================== 辅助函数 ====================
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

# 1. 选择数据类型 - 只显示有数据的类型
available_types = []

# 检查每种数据类型是否有数据
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
    st.sidebar.error("没有可用数据")
    st.warning("所有数据源都没有数据，请返回主页面重新加载数据。")
    st.stop()
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
    # 根据选择的数据类型获取数据
    if fixture_type == "TIMECHARTER":
        data = tc_spot
    elif fixture_type == "PERIOD":
        data = period_spot
    elif fixture_type == "VOYAGE GRAIN":
        data = vcgr_spot
    elif fixture_type == "VOYAGE COAL":
        data = vcco_spot
    elif fixture_type == "VOYAGE MISC":
        data = vcmi_spot
    elif fixture_type == "VOYAGE ORE":
        data = vcor_spot
    
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
    
    if data is not None and not data.empty:
        latest_date = data.index.max()
        st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
        
        latest_data = get_latest_data(data, fixture_type)
        
        if not latest_data.empty:
            # 这里可以继续您原来的筛选和显示逻辑
            # 为了保持代码简洁，我这里只显示简单版本
            
            st.info(f"今日共 {len(latest_data)} 条记录")
            
            # 显示前10条数据
            st.dataframe(
                latest_data.head(10),
                use_container_width=True
            )
            
            # 提供下载
            csv = latest_data.to_csv(index=True)
            st.download_button(
                label="📥 下载今日数据",
                data=csv,
                file_name=f"{fixture_type.lower().replace(' ', '_')}_{latest_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("今日暂无数据")
    else:
        st.warning(f"{fixture_type} 数据为空")

# ==================== 显示当前数据状态 ====================
with st.expander("📋 查看所有数据状态"):
    st.write("**数据加载状态:**")
    
    data_status = {
        "TIMECHARTER": tc_spot,
        "PERIOD": period_spot,
        "VOYAGE GRAIN": vcgr_spot,
        "VOYAGE COAL": vcco_spot,
        "VOYAGE MISC": vcmi_spot,
        "VOYAGE ORE": vcor_spot
    }
    
    for name, data in data_status.items():
        if data is None:
            st.write(f"❌ **{name}**: 数据未加载")
        elif data.empty:
            st.write(f"⚠️ **{name}**: 数据为空")
        else:
            st.write(f"✅ **{name}**: {len(data)} 条记录，最新日期: {data.index[-1].date()}")
