import streamlit as st
import pandas as pd
from datetime import date

st.title('Baltic Exchange Fixtures Dashboard')

# ==================== 更宽容的数据检查 ====================
def check_any_data_loaded():
    """检查是否有任何数据已加载（更宽容的检查）"""
    all_data_keys = ['tc_spot', 'period_spot', 'vcgr_spot', 'vcco_spot', 'vcmi_spot', 'vcor_spot']
    
    # 检查是否有至少一个数据已加载且不为空
    loaded_data = []
    for data_name in all_data_keys:
        if data_name in st.session_state and st.session_state[data_name] is not None:
            if hasattr(st.session_state[data_name], 'empty') and not st.session_state[data_name].empty:
                loaded_data.append((data_name, "有数据"))
            else:
                loaded_data.append((data_name, "已加载但为空"))
        else:
            loaded_data.append((data_name, "未加载"))
    
    # 只要有任何数据已加载（即使为空），就认为有数据
    has_any_data = any(name in st.session_state and st.session_state[name] is not None 
                       for name in all_data_keys)
    
    return has_any_data, loaded_data

# 检查数据加载状态
has_any_data, data_status = check_any_data_loaded()

if not has_any_data:
    st.markdown('# **:red[⚠️ 数据未加载]**')
    st.markdown('## **请先返回主页面加载数据**')
    
    st.info("""
    **解决方案：**
    1. 请点击左侧边栏的 **←** 按钮返回主页
    2. 或者使用顶部的导航菜单返回主页面
    3. 在主页面点击 **Update Data** 按钮加载数据
    4. 数据加载完成后，再返回此页面
    """)
    
    if st.button("🏠 返回主页面"):
        st.info("请使用浏览器返回按钮或侧边栏导航返回主页面")
    
    st.stop()

# ==================== 如果数据已加载，继续执行 ====================
st.success("✅ 数据加载完成！")

# 实际数据变量 - 从session_state获取，但允许为空
tc_spot = st.session_state.get('tc_spot')
period_spot = st.session_state.get('period_spot')
vcgr_spot = st.session_state.get('vcgr_spot')
vcco_spot = st.session_state.get('vcco_spot')
vcmi_spot = st.session_state.get('vcmi_spot')
vcor_spot = st.session_state.get('vcor_spot')

# 显示数据状态概览
st.subheader("📊 数据状态概览")

# 显示每个数据源的状态
cols = st.columns(3)
data_status_info = [
    ("TIMECHARTER", tc_spot),
    ("PERIOD", period_spot),
    ("VOYAGE GRAIN", vcgr_spot),
    ("VOYAGE COAL", vcco_spot),
    ("VOYAGE MISC", vcmi_spot),
    ("VOYAGE ORE", vcor_spot)
]

for idx, (name, data) in enumerate(data_status_info):
    col_idx = idx % 3
    if data is None:
        cols[col_idx].error(f"❌ {name}: 未加载")
    elif hasattr(data, 'empty') and data.empty:
        cols[col_idx].warning(f"⚠️ {name}: 数据为空")
    else:
        cols[col_idx].success(f"✅ {name}: {len(data)} 条记录")

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

# 1. 选择数据类型 - 只显示有数据（非空）的类型
available_types = []

# 检查每种数据类型是否有数据（非空）
data_mapping = [
    ("TIMECHARTER", tc_spot),
    ("PERIOD", period_spot),
    ("VOYAGE GRAIN", vcgr_spot),
    ("VOYAGE COAL", vcco_spot),
    ("VOYAGE MISC", vcmi_spot),
    ("VOYAGE ORE", vcor_spot)
]

for name, data in data_mapping:
    if data is not None and hasattr(data, 'empty') and not data.empty:
        available_types.append(name)

if not available_types:
    st.sidebar.error("没有可用数据")
    st.warning("所有数据源都没有数据，请返回主页面重新加载数据。")
    
    # 显示数据加载详情
    with st.expander("📋 查看数据加载详情"):
        for name, data in data_mapping:
            if data is None:
                st.write(f"❌ **{name}**: 未加载")
            elif hasattr(data, 'empty') and data.empty:
                st.write(f"⚠️ **{name}**: 已加载但为空")
            else:
                st.write(f"✅ **{name}**: {len(data)} 条记录")
    
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

# 添加Australia港口筛选说明
with st.sidebar.expander("Australia港口筛选说明"):
    st.write("""
    **筛选逻辑：**
    - TIMECHARTER/PERIOD: 检查 deliveryPort, loadArea, via, redel 字段
    - VOYAGE类型: 检查 loadArea, loadPort, dischargePort 字段
    
    **当前识别的Australia关键词：**
    - 国家/地区: AUSTRALIA, AUS, WA, QLD, NSW, VIC等
    - 主要港口: SYDNEY, MELBOURNE, BRISBANE, PERTH等
    - 矿石港口: PORT HEDLAND, DAMPIER, HAY POINT等
    
    **维护说明：**
    如需添加新的Australia港口关键词，请在代码中的 `australian_keywords` 列表中添加。
    """)

# ==================== 主显示逻辑 ====================
if fixture_type == "TIMECHARTER":
    data = tc_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
elif fixture_type == "PERIOD":
    data = period_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
elif fixture_type == "VOYAGE GRAIN":
    data = vcgr_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
elif fixture_type == "VOYAGE COAL":
    data = vcco_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
elif fixture_type == "VOYAGE MISC":
    data = vcmi_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
elif fixture_type == "VOYAGE ORE":
    data = vcor_spot
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")

# 现在显示选中的数据
if data is None:
    st.error(f"❌ {fixture_type} 数据未加载，请返回主页面重新加载。")
elif data.empty:
    st.warning(f"⚠️ {fixture_type} 数据为空，没有可显示的内容。")
else:
    latest_date = data.index.max()
    st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
    
    # 获取最新一天的数据
    latest_data = get_latest_data(data, fixture_type)
    
    # 统计信息
    total_records = len(latest_data)
    st.info(f"今日共 {total_records} 条记录")
    
    # ========== 筛选器 ==========
    st.subheader("🔍 筛选选项")
    
    # 根据数据类型显示不同的筛选器
    if fixture_type in ["TIMECHARTER", "PERIOD"]:
        # TIMECHARTER 和 PERIOD 的筛选器
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'deliveryPort' in latest_data.columns and not latest_data['deliveryPort'].dropna().empty:
                all_delivery_ports = sorted(latest_data['deliveryPort'].dropna().unique())
                selected_delivery_ports = st.multiselect(
                    "Delivery Ports",
                    options=all_delivery_ports,
                    default=all_delivery_ports[:5] if len(all_delivery_ports) > 5 else all_delivery_ports,
                    help="选择要显示的交付港口"
                )
            else:
                selected_delivery_ports = []
                st.info("Delivery Ports: 无数据")
        
        with col2:
            if 'loadArea' in latest_data.columns and not latest_data['loadArea'].dropna().empty:
                all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                selected_load_areas = st.multiselect(
                    "Load Areas",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas,
                    help="选择要显示的装载区域"
                )
            else:
                selected_load_areas = []
                st.info("Load Areas: 无数据")
        
        with col3:
            if 'VESSEL TYPE' in latest_data.columns and not latest_data['VESSEL TYPE'].dropna().empty:
                all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                selected_vessel_types = st.multiselect(
                    "Vessel Types",
                    options=all_vessel_types,
                    default=all_vessel_types,
                    help="选择要显示的船舶类型"
                )
            else:
                selected_vessel_types = []
                st.info("Vessel Types: 无数据")
        
        # 第二行筛选器
        col4, col5, col6 = st.columns(3)
        
        # 根据是否是 TIMECHARTER 显示不同的筛选器
        if fixture_type == "TIMECHARTER":
            with col4:
                if 'via' in latest_data.columns and not latest_data['via'].dropna().empty:
                    all_via = sorted(latest_data['via'].dropna().unique())
                    selected_via = st.multiselect(
                        "Via Ports",
                        options=all_via,
                        default=all_via[:5] if len(all_via) > 5 else all_via,
                        help="选择要显示的中转港口"
                    )
                else:
                    selected_via = []
                    st.info("Via Ports: 无数据")
        
        with col5:
            if 'redel' in latest_data.columns and not latest_data['redel'].dropna().empty:
                all_redel = sorted(latest_data['redel'].dropna().unique())
                selected_redel = st.multiselect(
                    "Redelivery Ports",
                    options=all_redel,
                    default=all_redel[:5] if len(all_redel) > 5 else all_redel,
                    help="选择要显示的还船港口"
                )
            else:
                selected_redel = []
                st.info("Redelivery Ports: 无数据")
        
        with col6:
            if 'charterer' in latest_data.columns and not latest_data['charterer'].dropna().empty:
                all_charterers = sorted(latest_data['charterer'].dropna().unique())
                selected_charterers = st.multiselect(
                    "Charterers",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers,
                    help="选择要显示的租船人"
                )
            else:
                selected_charterers = []
                st.info("Charterers: 无数据")
        
        # ========== 应用基础筛选 ==========
        filtered_data = latest_data.copy()
        
        if selected_delivery_ports:
            filtered_data = filtered_data[filtered_data['deliveryPort'].isin(selected_delivery_ports) | filtered_data['deliveryPort'].isna()]
        
        if selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if fixture_type == "TIMECHARTER" and selected_via:
            filtered_data = filtered_data[filtered_data['via'].isin(selected_via) | filtered_data['via'].isna()]
        
        if selected_redel:
            filtered_data = filtered_data[filtered_data['redel'].isin(selected_redel) | filtered_data['redel'].isna()]
        
        if selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
    
    else:
        # VOYAGE类型的筛选器
        col1, col2 = st.columns(2)
        
        with col1:
            if 'loadArea' in latest_data.columns and not latest_data['loadArea'].dropna().empty:
                all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                selected_load_areas = st.multiselect(
                    "Load Areas",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas
                )
            else:
                selected_load_areas = []
                st.info("Load Areas: 无数据")
            
            if 'loadPort' in latest_data.columns and not latest_data['loadPort'].dropna().empty:
                all_load_ports = sorted(latest_data['loadPort'].dropna().unique())
                selected_load_ports = st.multiselect(
                    "Load Ports",
                    options=all_load_ports,
                    default=all_load_ports[:5] if len(all_load_ports) > 5 else all_load_ports
                )
            else:
                selected_load_ports = []
                st.info("Load Ports: 无数据")
        
        with col2:
            if 'dischargePort' in latest_data.columns and not latest_data['dischargePort'].dropna().empty:
                all_discharge_ports = sorted(latest_data['dischargePort'].dropna().unique())
                selected_discharge_ports = st.multiselect(
                    "Discharge Ports",
                    options=all_discharge_ports,
                    default=all_discharge_ports[:5] if len(all_discharge_ports) > 5 else all_discharge_ports
                )
            else:
                selected_discharge_ports = []
                st.info("Discharge Ports: 无数据")
            
            if 'VESSEL TYPE' in latest_data.columns and not latest_data['VESSEL TYPE'].dropna().empty:
                all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                selected_vessel_types = st.multiselect(
                    "Vessel Types",
                    options=all_vessel_types,
                    default=all_vessel_types
                )
            else:
                selected_vessel_types = []
                st.info("Vessel Types: 无数据")
        
        # 第三行筛选器
        col3, col4 = st.columns(2)
        
        with col3:
            if 'charterer' in latest_data.columns and not latest_data['charterer'].dropna().empty:
                all_charterers = sorted(latest_data['charterer'].dropna().unique())
                selected_charterers = st.multiselect(
                    "Charterers",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers
                )
            else:
                selected_charterers = []
                st.info("Charterers: 无数据")
        
        with col4:
            if 'cargoSize' in latest_data.columns and not latest_data['cargoSize'].dropna().empty:
                all_cargo_sizes = sorted(latest_data['cargoSize'].dropna().unique())
                selected_cargo_sizes = st.multiselect(
                    "Cargo Sizes",
                    options=all_cargo_sizes,
                    default=all_cargo_sizes[:5] if len(all_cargo_sizes) > 5 else all_cargo_sizes
                )
            else:
                selected_cargo_sizes = []
                st.info("Cargo Sizes: 无数据")
        
        # ========== 应用基础筛选 ==========
        filtered_data = latest_data.copy()
        
        if selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if selected_load_ports:
            filtered_data = filtered_data[filtered_data['loadPort'].isin(selected_load_ports) | filtered_data['loadPort'].isna()]
        
        if selected_discharge_ports:
            filtered_data = filtered_data[filtered_data['dischargePort'].isin(selected_discharge_ports) | filtered_data['dischargePort'].isna()]
        
        if selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
        
        if selected_cargo_sizes:
            filtered_data = filtered_data[filtered_data['cargoSize'].isin(selected_cargo_sizes) | filtered_data['cargoSize'].isna()]
    
    # ========== 应用Australia筛选 ==========
    if show_australia_only:
        # 应用Australia港口筛选
        australia_mask = filtered_data.apply(lambda row: contains_australian_info(row, fixture_type), axis=1)
        filtered_data = filtered_data[australia_mask]
        
        # 显示筛选统计
        australia_count = len(filtered_data)
        st.warning(f"**Australia相关港口筛选已启用** - 显示 {australia_count} 条Australia相关记录")
    
    # ========== 显示数据 ==========
    st.subheader(f"📊 筛选结果 ({len(filtered_data)} 条记录)")
    
    if not filtered_data.empty:
        # 选择要显示的列
        available_columns = filtered_data.columns.tolist()
        
        # 根据数据类型推荐显示的列
        if fixture_type == "TIMECHARTER":
            recommended_columns = ['shipName', 'dwt', 'VESSEL TYPE', 'deliveryPort', 
                                 'loadArea', 'via', 'redel', 'hire', 'charterer', 
                                 'comment', 'buildYear', 'freeText']
        elif fixture_type == "PERIOD":
            recommended_columns = ['shipName', 'dwt', 'VESSEL TYPE', 'deliveryPort', 
                                 'loadArea', 'redel', 'hire', 'charterer', 'comment', 
                                 'freeText', 'buildYear']
        else:  # VOYAGE类型
            recommended_columns = ['shipName', 'cargoSize', 'dwt', 'VESSEL TYPE', 
                                 'loadPort', 'loadArea', 'dischargePort', 'freight', 
                                 'charterer', 'comment', 'buildYear', 'freeText']
        
        # 确保推荐的列都存在
        default_columns = [col for col in recommended_columns if col in available_columns]
        
        # 如果没有默认列，使用所有可用列
        if not default_columns:
            default_columns = available_columns[:8]  # 显示前8列
        
        visible_columns = st.multiselect(
            "选择显示的列",
            options=available_columns,
            default=default_columns
        )
        
        if visible_columns:
            display_data = filtered_data[visible_columns]
            
            # 高亮Australia相关港口
            if show_australia_only:
                # 对Australia港口进行高亮
                def highlight_australian(val):
                    if pd.isna(val):
                        return ''
                    if is_australian_port(val):
                        return f'<span style="background-color: #FFE5B4; font-weight: bold;">{val}</span>'
                    return val
                
                # 应用高亮
                styled_df = display_data.copy()
                if fixture_type in ["TIMECHARTER", "PERIOD"]:
                    highlight_cols = ['deliveryPort', 'loadArea', 'via', 'redel']
                else:
                    highlight_cols = ['loadPort', 'loadArea', 'dischargePort']
                
                for col in highlight_cols:
                    if col in styled_df.columns:
                        styled_df[col] = styled_df[col].apply(highlight_australian)
                
                # 显示高亮后的表格
                st.markdown(styled_df.to_html(escape=False), unsafe_allow_html=True)
            else:
                # 普通显示
                st.dataframe(
                    display_data,
                    use_container_width=True,
                    height=400
                )
            
            # 统计信息
            st.metric("筛选后记录数", len(filtered_data))
            
            # 提供下载选项
            csv = filtered_data.to_csv(index=True)
            st.download_button(
                label="📥 下载筛选数据为 CSV",
                data=csv,
                file_name=f"{fixture_type.lower().replace(' ', '_')}_fixtures_{latest_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                help="下载当前筛选结果"
            )
        else:
            st.warning("请选择至少一列进行显示")
    else:
        st.warning("没有匹配筛选条件的记录")

# ==================== 侧边栏统计信息 ====================
st.sidebar.markdown("---")
st.sidebar.subheader("📈 数据统计")

# 显示当前数据类型的统计信息
if data is not None and not data.empty:
    st.sidebar.write(f"**数据类型:** {fixture_type}")
    st.sidebar.write(f"**总记录数:** {len(data)}")
    
    latest_date = data.index.max()
    st.sidebar.write(f"**最新数据日期:** {latest_date.strftime('%Y-%m-%d')}")
    
    # 按日期统计
    date_counts = data.groupby(data.index.date).size()
    if len(date_counts) > 0:
        st.sidebar.write(f"**最近7天平均每日记录:** {date_counts.tail(7).mean():.1f}")
    
    # Australia相关统计
    if show_australia_only and 'filtered_data' in locals():
        australia_percentage = (len(filtered_data) / len(latest_data)) * 100 if len(latest_data) > 0 else 0
        st.sidebar.write(f"**Australia记录占比:** {australia_percentage:.1f}%")
else:
    st.sidebar.warning(f"**{fixture_type}**: 无数据")

# ==================== Australia港口维护说明 ====================
with st.expander("🛠️ Australia港口关键词维护说明"):
    st.write("""
    ### 如何添加新的Australia港口关键词
    
    在代码的 `is_australian_port` 函数中，找到 `australian_keywords` 列表，
    按照以下格式添加新的港口关键词：
    
    ```python
    australian_keywords = [
        # 现有关键词...
        
        # 新添加的港口关键词
        'YOUR_NEW_PORT', 'ANOTHER_PORT',
    ]
    ```
    
    ### 添加原则：
    1. **全大写**：所有关键词都应使用大写字母
    2. **完整名称**：添加港口的完整名称（如 'PORT HEDLAND'）
    3. **缩写**：如有常见缩写，也一并添加（如 'WA' 代表 Western Australia）
    4. **变体**：考虑不同的拼写变体
    
    ### 当前已包含的关键词类别：
    1. 国家/地区名称 (AUSTRALIA, AUS, WA, QLD等)
    2. 主要城市港口 (SYDNEY, MELBOURNE等)
    3. 重要港口城市 (NEWCASTLE, FREMANTLE等)
    4. 矿石/煤炭港口 (PORT HEDLAND, DAMPIER等)
    5. 其他常见港口
    
    ### 测试新关键词：
    添加新关键词后，重启应用并测试是否能够正确识别新的Australia港口。
    """)
    
    # 显示当前Australia港口关键词数量
    australian_keywords = [
        'AUSTRALIA', 'AUS', 'WESTERN AUSTRALIA', 'WA', 'QUEENSLAND', 'QLD',
        'NEW SOUTH WALES', 'NSW', 'VICTORIA', 'VIC', 'SOUTH AUSTRALIA', 'SA',
        'TASMANIA', 'TAS', 'NORTHERN TERRITORY', 'NT', 'SYDNEY', 'MELBOURNE',
        'BRISBANE', 'PERTH', 'ADELAIDE', 'DARWIN', 'HOBART', 'NEWCASTLE',
        'FREMANTLE', 'GEELONG', 'PORT KEMBLA', 'TOWNSVILLE', 'CAIRNS',
        'GLADSTONE', 'MACKAY', 'BUNBURY', 'ESPERANCE', 'ALBANY', 'PORT LINCOLN',
        'PORT HEDLAND', 'DAMPIER', 'HAY POINT', 'ABBOT POINT', 'PORT WALCOTT',
        'CAPE LAMBERT', 'PORT ALMA', 'PORT BOTANY', 'PORT OF BRISBANE',
        'PORT OF MELBOURNE', 'PORT OF ADELAIDE', 'PORT OF FREMANTLE',
        'WEIPA', 'GOVE', 'KARRATHA', 'GERALDTON', 'BROOME', 'PORTLAND',
        'BURNIE', 'DEVONPORT', 'PORT PIRIE', 'WHYALLA', 'PORT GILES'
    ]
    
    st.write(f"**当前Australia关键词数量:** {len(australian_keywords)}")
    st.write("**完整关键词列表:**")
    st.code(", ".join(sorted(australian_keywords)))
