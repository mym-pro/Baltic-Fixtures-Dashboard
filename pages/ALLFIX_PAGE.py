"""
新.FIXTURE_PAGE.ALLFIX_PAGE 的 Docstring
1. 在FISTURE_PROCESS中的load_tc_data() 函数已经将历史数据从 timecharter.csv 加载并与新数据合并了
那么
tc_spot=load_tc_data(days_back)
if 'tc_spot' not in st.session_state:
    st.session_state['tc_spot']=tc_spot
返回的 tc_spot 包含了所有历史数据
然后这个 tc_spot 被存储在 st.session_state['tc_spot'] 中
tc_spot中已经包含了tccharter.csv中的所有数据以及dasback（默认为更新两天，点update时会向前拉取15天）的最新数据整合的数据（即全部数据）
2. 在页面中，使用tc_spot = st.session_state['tc_spot']就是加载了session中的数据到tc_spot，就可以直接使用了

"""






import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date
from datetime import timedelta
from dateutil import relativedelta
from pandas.tseries.offsets import BDay

st.title('Baltic Exchange Fixtures Dashboard')


# 实际数据变量
if 'tc_spot' not in st.session_state:
    st.markdown('# **:red[！ERROR]**')
    st.markdown('## **:red[请返回第一个标签页FIXTURE_PROCESS加载数据]**')
    st.stop()

tc_spot = st.session_state['tc_spot']
period_spot = st.session_state['period_spot']
vcgr_spot = st.session_state['vcgr_spot']
vcco_spot = st.session_state['vcco_spot']
vcmi_spot = st.session_state['vcmi_spot']
vcor_spot = st.session_state['vcor_spot']

# ==================== 辅助函数 ====================
def is_australian_port(port_name):
    """检查港口是否为Australia相关港口"""
    if pd.isna(port_name):
        return False
    
    # Australia港口关键词列表 (可以随时添加)
    australian_keywords = [
        # 国家/地区名称
        'AUSTRALIA', 'AUS', 
        'WESTERN AUSTRALIA', 'WA',
        'QUEENSLAND', 'QLD',
        'NEW SOUTH WALES', 'NSW',
        'VICTORIA', 'VIC',
        'SOUTH AUSTRALIA', 'SA',
        'TASMANIA', 'TAS',
        'NORTHERN TERRITORY', 'NT',
        
        # 主要城市港口
        'SYDNEY', 'MELBOURNE', 'BRISBANE', 'PERTH',
        'ADELAIDE', 'DARWIN', 'HOBART', 
        
        # 重要港口城市
        'NEWCASTLE', 'FREMANTLE', 'GEELONG', 'PORT KEMBLA',
        'TOWNSVILLE', 'CAIRNS', 'GLADSTONE', 'MACKAY', 
        'BUNBURY', 'ESPERANCE', 'ALBANY', 'PORT LINCOLN',
        
        # 矿石/煤炭港口
        'PORT HEDLAND', 'DAMPIER', 'HAY POINT', 'ABBOT POINT',
        'PORT WALCOTT', 'CAPE LAMBERT', 'PORT ALMA',
        'PORT BOTANY', 'PORT OF BRISBANE', 'PORT OF MELBOURNE',
        'PORT OF ADELAIDE', 'PORT OF FREMANTLE',
        
        # 其他常见港口
        'WEIPA', 'GOVE', 'KARRATHA', 'GERALDTON',
        'BROOME', 'PORTLAND', 'BURNIE', 'DEVONPORT',
        'PORT PIRIE', 'WHYALLA', 'PORT GILES'
    ]
    
    # 转换为大写进行比较
    port_str = str(port_name).upper()
    
    # 检查是否包含任何Australia关键词
    for keyword in australian_keywords:
        if keyword in port_str:
            return True
    
    return False

def contains_australian_info(row, fixture_type):
    """检查一行数据是否包含Australia相关信息"""
    if fixture_type in ["TIMECHARTER", "PERIOD"]:
        # 检查这些字段是否包含Australia港口
        fields_to_check = ['deliveryPort', 'loadArea', 'via', 'redel']
        for field in fields_to_check:
            if field in row and is_australian_port(row[field]):
                return True
    else:  # VOYAGE类型
        # 检查这些字段是否包含Australia港口
        fields_to_check = ['loadArea', 'loadPort', 'dischargePort']
        for field in fields_to_check:
            if field in row and is_australian_port(row[field]):
                return True
    
    return False

def get_latest_data(data, fixture_type_name):
    """获取最新一天的数据"""
    if data is None or data.empty:
        return pd.DataFrame()
    
    # 获取最新日期
    latest_date = data.index.max()
    latest_data = data[data.index == latest_date].copy()
    latest_data['fixtureType'] = fixture_type_name
    return latest_data

# ==================== 数据加载检查 ====================
def check_data_loaded(data_dict):
    """检查数据是否已加载"""
    for name, data in data_dict.items():
        if data is None:
            st.markdown(f'# **:red[！ERROR]**')
            st.markdown(f'## **:red[{name}数据未加载，请返回第一个标签页FIXTURE_PROCESS重新加载数据]**')
            return False
    return True

# 检查所有数据
data_sources = {
    'TIMECHARTER': ('tc_spot', tc_spot if 'tc_spot' in st.session_state else None),
    'PERIOD': ('period_spot', period_spot if 'period_spot' in st.session_state else None),
    'VOYAGE GRAIN': ('vcgr_spot', vcgr_spot if 'vcgr_spot' in st.session_state else None),
    'VOYAGE COAL': ('vcco_spot', vcco_spot if 'vcco_spot' in st.session_state else None),
    'VOYAGE MISC': ('vcmi_spot', vcmi_spot if 'vcmi_spot' in st.session_state else None),
    'VOYAGE ORE': ('vcor_spot', vcor_spot if 'vcor_spot' in st.session_state else None),
}


# ==================== 侧边栏配置 ====================
st.sidebar.title("📊 筛选选项")

# 1. 选择数据类型
fixture_type = st.sidebar.selectbox(
    "选择数据类型",
    ["TIMECHARTER", "PERIOD", "VOYAGE GRAIN", "VOYAGE COAL", "VOYAGE MISC", "VOYAGE ORE"]
)

# 2. Australia港口筛选选项
st.sidebar.markdown("---")
st.sidebar.subheader("🇦🇺 Australia港口筛选")

# 添加Australia港口筛选开关
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
# 根据选择的类型显示数据
if fixture_type == "TIMECHARTER":
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
    data = tc_spot
    
    if data is not None and not data.empty:
        latest_date = data.index.max()
        st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
        
        # 获取最新一天的数据
        latest_data = get_latest_data(data, fixture_type)
        
        # 统计信息
        total_records = len(latest_data)
        st.info(f"今日共 {total_records} 条记录")
        
        # ========== 筛选器 ==========
        st.subheader("🔍 筛选选项")
        
        # 第一行筛选器
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # deliveryPort 筛选
            if 'deliveryPort' in latest_data.columns:
                all_delivery_ports = sorted(latest_data['deliveryPort'].dropna().unique())
                selected_delivery_ports = st.multiselect(
                    "Delivery Ports",
                    options=all_delivery_ports,
                    default=all_delivery_ports[:5] if len(all_delivery_ports) > 5 else all_delivery_ports,
                    help="选择要显示的交付港口"
                )
        
        with col2:
            # loadArea 筛选
            if 'loadArea' in latest_data.columns:
                all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                selected_load_areas = st.multiselect(
                    "Load Areas",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas,
                    help="选择要显示的装载区域"
                )
        
        with col3:
            # VESSEL TYPE 筛选
            if 'VESSEL TYPE' in latest_data.columns:
                all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                selected_vessel_types = st.multiselect(
                    "Vessel Types",
                    options=all_vessel_types,
                    default=all_vessel_types,
                    help="选择要显示的船舶类型"
                )
        
        # 第二行筛选器
        col4, col5, col6 = st.columns(3)
        
        with col4:
            # via 筛选
            if 'via' in latest_data.columns:
                all_via = sorted(latest_data['via'].dropna().unique())
                selected_via = st.multiselect(
                    "Via Ports",
                    options=all_via,
                    default=all_via[:5] if len(all_via) > 5 else all_via,
                    help="选择要显示的中转港口"
                )
        
        with col5:
            # redel 筛选
            if 'redel' in latest_data.columns:
                all_redel = sorted(latest_data['redel'].dropna().unique())
                selected_redel = st.multiselect(
                    "Redelivery Ports",
                    options=all_redel,
                    default=all_redel[:5] if len(all_redel) > 5 else all_redel,
                    help="选择要显示的还船港口"
                )
        
        with col6:
            # charterer 筛选
            if 'charterer' in latest_data.columns:
                all_charterers = sorted(latest_data['charterer'].dropna().unique())
                selected_charterers = st.multiselect(
                    "Charterers",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers,
                    help="选择要显示的租船人"
                )
        
        # ========== 应用基础筛选 ==========
        filtered_data = latest_data.copy()
        
        if 'deliveryPort' in filtered_data.columns and selected_delivery_ports:
            filtered_data = filtered_data[filtered_data['deliveryPort'].isin(selected_delivery_ports) | filtered_data['deliveryPort'].isna()]
        
        if 'loadArea' in filtered_data.columns and selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if 'VESSEL TYPE' in filtered_data.columns and selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if 'via' in filtered_data.columns and selected_via:
            filtered_data = filtered_data[filtered_data['via'].isin(selected_via) | filtered_data['via'].isna()]
        
        if 'redel' in filtered_data.columns and selected_redel:
            filtered_data = filtered_data[filtered_data['redel'].isin(selected_redel) | filtered_data['redel'].isna()]
        
        if 'charterer' in filtered_data.columns and selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
        
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
            
            # TIMECHARTER推荐显示的列
            timecharter_columns = [
                'shipName', 'dwt', 'VESSEL TYPE', 'deliveryPort', 
                'loadArea', 'via', 'redel', 'hire', 'charterer', 
                'comment', 'buildYear', 'freeText'
            ]
            
            # 确保推荐的列都存在
            default_columns = [col for col in timecharter_columns if col in available_columns]
            
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
                    for col in ['deliveryPort', 'loadArea', 'via', 'redel']:
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
                    file_name=f"timecharter_fixtures_{latest_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    help="下载当前筛选结果"
                )
            else:
                st.warning("请选择至少一列进行显示")
        else:
            st.warning("没有匹配筛选条件的记录")
    else:
        st.warning("暂无数据")

elif fixture_type == "PERIOD":
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
    data = period_spot
    
    if data is not None and not data.empty:
        latest_date = data.index.max()
        st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
        
        # 获取最新一天的数据
        latest_data = get_latest_data(data, fixture_type)
        
        # 统计信息
        total_records = len(latest_data)
        st.info(f"今日共 {total_records} 条记录")
        
        # ========== 筛选器 ==========
        st.subheader("🔍 筛选选项")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'deliveryPort' in latest_data.columns:
                all_delivery_ports = sorted(latest_data['deliveryPort'].dropna().unique())
                selected_delivery_ports = st.multiselect(
                    "Delivery Ports",
                    options=all_delivery_ports,
                    default=all_delivery_ports[:5] if len(all_delivery_ports) > 5 else all_delivery_ports
                )
        
        with col2:
            if 'loadArea' in latest_data.columns:
                all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                selected_load_areas = st.multiselect(
                    "Load Areas",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas
                )
        
        with col3:
            if 'VESSEL TYPE' in latest_data.columns:
                all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                selected_vessel_types = st.multiselect(
                    "Vessel Types",
                    options=all_vessel_types,
                    default=all_vessel_types
                )
        
        col4, col5 = st.columns(2)
        
        with col4:
            if 'redel' in latest_data.columns:
                all_redel = sorted(latest_data['redel'].dropna().unique())
                selected_redel = st.multiselect(
                    "Redelivery Ports",
                    options=all_redel,
                    default=all_redel[:5] if len(all_redel) > 5 else all_redel
                )
        
        with col5:
            if 'charterer' in latest_data.columns:
                all_charterers = sorted(latest_data['charterer'].dropna().unique())
                selected_charterers = st.multiselect(
                    "Charterers",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers
                )
        
        # ========== 应用基础筛选 ==========
        filtered_data = latest_data.copy()
        
        if 'deliveryPort' in filtered_data.columns and selected_delivery_ports:
            filtered_data = filtered_data[filtered_data['deliveryPort'].isin(selected_delivery_ports) | filtered_data['deliveryPort'].isna()]
        
        if 'loadArea' in filtered_data.columns and selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if 'VESSEL TYPE' in filtered_data.columns and selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if 'redel' in filtered_data.columns and selected_redel:
            filtered_data = filtered_data[filtered_data['redel'].isin(selected_redel) | filtered_data['redel'].isna()]
        
        if 'charterer' in filtered_data.columns and selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
        
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
            # 显示PERIOD特有的字段
            available_columns = filtered_data.columns.tolist()
            period_columns = ['shipName', 'dwt', 'VESSEL TYPE', 'deliveryPort', 
                             'loadArea', 'redel', 'hire', 'charterer', 'comment', 
                             'freeText', 'buildYear']
            
            # 过滤掉不存在的列
            visible_columns_options = [col for col in period_columns if col in available_columns]
            
            # 添加其他可用列
            other_columns = [col for col in available_columns if col not in visible_columns_options]
            visible_columns_options.extend(other_columns)
            
            visible_columns = st.multiselect(
                "选择显示的列",
                options=visible_columns_options,
                default=[col for col in period_columns[:6] if col in available_columns]
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
                    for col in ['deliveryPort', 'loadArea', 'redel']:
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
                
                # 下载选项
                csv = filtered_data.to_csv(index=True)
                st.download_button(
                    label="📥 下载筛选数据为 CSV",
                    data=csv,
                    file_name=f"period_fixtures_{latest_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("请选择至少一列进行显示")
        else:
            st.warning("没有匹配筛选条件的记录")
    else:
        st.warning("暂无数据")

else:
    # ========== VOYAGE类型数据处理 ==========
    voyage_types = {
        "VOYAGE GRAIN": vcgr_spot,
        "VOYAGE COAL": vcco_spot,
        "VOYAGE MISC": vcmi_spot,
        "VOYAGE ORE": vcor_spot
    }
    
    data = voyage_types[fixture_type]
    st.header(f"📋 {fixture_type} Fixtures - 最新数据")
    
    if data is not None and not data.empty:
        latest_date = data.index.max()
        st.success(f"最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
        
        # 获取最新一天的数据
        latest_data = get_latest_data(data, fixture_type)
        
        # 统计信息
        total_records = len(latest_data)
        st.info(f"今日共 {total_records} 条记录")
        
        # ========== VOYAGE类型的筛选器 ==========
        st.subheader("🔍 筛选选项")
        col1, col2 = st.columns(2)
        
        with col1:
            # loadArea 筛选
            if 'loadArea' in latest_data.columns:
                all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                selected_load_areas = st.multiselect(
                    "Load Areas",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas
                )
            
            # loadPort 筛选
            if 'loadPort' in latest_data.columns:
                all_load_ports = sorted(latest_data['loadPort'].dropna().unique())
                selected_load_ports = st.multiselect(
                    "Load Ports",
                    options=all_load_ports,
                    default=all_load_ports[:5] if len(all_load_ports) > 5 else all_load_ports
                )
        
        with col2:
            # dischargePort 筛选
            if 'dischargePort' in latest_data.columns:
                all_discharge_ports = sorted(latest_data['dischargePort'].dropna().unique())
                selected_discharge_ports = st.multiselect(
                    "Discharge Ports",
                    options=all_discharge_ports,
                    default=all_discharge_ports[:5] if len(all_discharge_ports) > 5 else all_discharge_ports
                )
            
            # VESSEL TYPE 筛选
            if 'VESSEL TYPE' in latest_data.columns:
                all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                selected_vessel_types = st.multiselect(
                    "Vessel Types",
                    options=all_vessel_types,
                    default=all_vessel_types
                )
        
        # 第三行筛选器
        col3, col4 = st.columns(2)
        
        with col3:
            # charterer 筛选
            if 'charterer' in latest_data.columns:
                all_charterers = sorted(latest_data['charterer'].dropna().unique())
                selected_charterers = st.multiselect(
                    "Charterers",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers
                )
        
        with col4:
            # cargoSize 筛选
            if 'cargoSize' in latest_data.columns:
                all_cargo_sizes = sorted(latest_data['cargoSize'].dropna().unique())
                selected_cargo_sizes = st.multiselect(
                    "Cargo Sizes",
                    options=all_cargo_sizes,
                    default=all_cargo_sizes[:5] if len(all_cargo_sizes) > 5 else all_cargo_sizes
                )
        
        # ========== 应用基础筛选 ==========
        filtered_data = latest_data.copy()
        
        if 'loadArea' in filtered_data.columns and selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if 'loadPort' in filtered_data.columns and selected_load_ports:
            filtered_data = filtered_data[filtered_data['loadPort'].isin(selected_load_ports) | filtered_data['loadPort'].isna()]
        
        if 'dischargePort' in filtered_data.columns and selected_discharge_ports:
            filtered_data = filtered_data[filtered_data['dischargePort'].isin(selected_discharge_ports) | filtered_data['dischargePort'].isna()]
        
        if 'VESSEL TYPE' in filtered_data.columns and selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if 'charterer' in filtered_data.columns and selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
        
        if 'cargoSize' in filtered_data.columns and selected_cargo_sizes:
            filtered_data = filtered_data[filtered_data['cargoSize'].isin(selected_cargo_sizes) | filtered_data['cargoSize'].isna()]
        
        # ========== 应用Australia筛选 ==========
        if show_australia_only:
            # 应用Australia港口筛选
            australia_mask = filtered_data.apply(lambda row: contains_australian_info(row, "VOYAGE"), axis=1)
            filtered_data = filtered_data[australia_mask]
            
            # 显示筛选统计
            australia_count = len(filtered_data)
            st.warning(f"**Australia相关港口筛选已启用** - 显示 {australia_count} 条Australia相关记录")
        
        # ========== 显示数据 ==========
        st.subheader(f"📊 筛选结果 ({len(filtered_data)} 条记录)")
        
        if not filtered_data.empty:
            # 显示VOYAGE特有的字段
            available_columns = filtered_data.columns.tolist()
            voyage_columns = ['shipName', 'cargoSize', 'dwt', 'VESSEL TYPE', 
                             'loadPort', 'loadArea', 'dischargePort', 'freight', 
                             'charterer', 'comment', 'buildYear', 'freeText']
            
            # 过滤掉不存在的列
            visible_columns_options = [col for col in voyage_columns if col in available_columns]
            
            # 添加其他可用列
            other_columns = [col for col in available_columns if col not in visible_columns_options]
            visible_columns_options.extend(other_columns)
            
            visible_columns = st.multiselect(
                "选择显示的列",
                options=visible_columns_options,
                default=[col for col in voyage_columns[:7] if col in available_columns]
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
                    for col in ['loadPort', 'loadArea', 'dischargePort']:
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
                
                # 下载选项
                csv = filtered_data.to_csv(index=True)
                st.download_button(
                    label="📥 下载筛选数据为 CSV",
                    data=csv,
                    file_name=f"{fixture_type.lower().replace(' ', '_')}_fixtures_{latest_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("请选择至少一列进行显示")
        else:
            st.warning("没有匹配筛选条件的记录")
    else:
        st.warning("暂无数据")

# ==================== 侧边栏统计信息 ====================
st.sidebar.markdown("---")
st.sidebar.subheader("📈 数据统计")

# 获取当前显示的数据用于统计
if fixture_type == "TIMECHARTER":
    data_for_stats = tc_spot
elif fixture_type == "PERIOD":
    data_for_stats = period_spot
elif fixture_type == "VOYAGE GRAIN":
    data_for_stats = vcgr_spot
elif fixture_type == "VOYAGE COAL":
    data_for_stats = vcco_spot
elif fixture_type == "VOYAGE MISC":
    data_for_stats = vcmi_spot
elif fixture_type == "VOYAGE ORE":
    data_for_stats = vcor_spot
else:
    data_for_stats = None

if data_for_stats is not None and not data_for_stats.empty:
    st.sidebar.write(f"**数据类型:** {fixture_type}")
    st.sidebar.write(f"**总记录数:** {len(data_for_stats)}")
    
    latest_date = data_for_stats.index.max()
    st.sidebar.write(f"**最新数据日期:** {latest_date.strftime('%Y-%m-%d')}")
    
    # 按日期统计
    date_counts = data_for_stats.groupby(data_for_stats.index.date).size()
    if len(date_counts) > 0:
        st.sidebar.write(f"**最近7天平均每日记录:** {date_counts.tail(7).mean():.1f}")
    
    # Australia相关统计
    if show_australia_only and 'filtered_data' in locals():
        australia_percentage = (len(filtered_data) / len(latest_data)) * 100 if len(latest_data) > 0 else 0
        st.sidebar.write(f"**Australia记录占比:** {australia_percentage:.1f}%")

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