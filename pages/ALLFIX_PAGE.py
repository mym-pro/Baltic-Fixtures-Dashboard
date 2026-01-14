import streamlit as st
import pandas as pd
from datetime import date, datetime
import json

st.set_page_config(layout="wide")
st.title('Baltic Exchange Fixtures Dashboard')

# ==================== 导入配置管理模块 ====================
try:
    from config_manager import get_custom_sets, get_all_sets_names, get_set_keywords, get_set, increment_usage_count
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    st.error("❌ 配置管理模块未找到，请确保 config_manager.py 文件存在")
    st.stop()

# ==================== 数据辅助函数 ====================
def contains_keywords(row, fixture_type, keyword_sets, logic="OR"):
    """
    通用关键词筛选函数
    
    参数:
    - row: DataFrame行数据
    - fixture_type: 数据类型（TIMECHARTER/PERIOD/VOYAGE）
    - keyword_sets: 字典，{集合名: [关键词列表]}
    - logic: "OR"（任一集合匹配）或"AND"（所有集合匹配）
    
    返回: bool
    """
    
    if not keyword_sets:
        return True
    
    # 确定要检查的字段
    if fixture_type in ["TIMECHARTER", "PERIOD"]:
        fields_to_check = ['deliveryPort', 'loadArea', 'via', 'redel']
    else:
        fields_to_check = ['loadArea', 'loadPort', 'dischargePort']
    
    # 过滤掉不存在的字段
    fields_to_check = [field for field in fields_to_check if field in row]
    
    # 根据逻辑进行筛选
    if logic == "OR":
        # OR逻辑：匹配任意集合的任意关键词
        for set_name, keywords in keyword_sets.items():
            if matches_keywords(row, fields_to_check, keywords):
                return True
        return False
    else:
        # AND逻辑：必须匹配所有集合
        for set_name, keywords in keyword_sets.items():
            if not matches_keywords(row, fields_to_check, keywords):
                return False
        return True

def matches_keywords(row, fields, keywords):
    """检查行数据是否包含指定关键词"""
    for field in fields:
        if field in row and not pd.isna(row[field]):
            port_str = str(row[field]).upper()
            for keyword in keywords:
                if keyword.upper() in port_str:
                    return True
    return False

def is_port_related(port_name, keywords):
    """检查港口是否包含指定关键词列表中的任意一个"""
    if pd.isna(port_name):
        return False
    
    port_str = str(port_name).upper()
    for keyword in keywords:
        if keyword.upper() in port_str:
            return True
    
    return False

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

# ==================== 基础筛选部分 ====================
with st.sidebar.expander("🔍 基础筛选", expanded=True):
    # 这里的内容将在选择数据类型后动态显示
    pass

# ==================== 自定义集合筛选部分 ====================
with st.sidebar.expander("🗂️ 自定义筛选集合", expanded=True):
    if not CONFIG_MANAGER_AVAILABLE:
        st.error("配置管理模块不可用")
    else:
        # 获取所有自定义集合
        custom_sets = get_custom_sets()
        
        if not custom_sets:
            st.info("📭 没有自定义筛选集合")
            st.markdown("请前往 **Data Manager** 页面创建您的第一个集合")
        else:
            # 按使用频率排序（使用次数多的靠前）
            sorted_sets = sorted(
                custom_sets.items(),
                key=lambda x: x[1].get("usage_count", 0),
                reverse=True
            )
            
            # 显示集合选择
            st.markdown("**选择筛选集合:**")
            
            selected_sets = {}
            for set_name, set_data in sorted_sets:
                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.checkbox(set_name, key=f"set_{set_name}"):
                        selected_sets[set_name] = set_data.get("keywords", [])
                with col2:
                    # 显示关键词数量
                    keyword_count = len(set_data.get("keywords", []))
                    st.markdown(f"<small>{keyword_count}个</small>", unsafe_allow_html=True)
            
            # 选择逻辑
            if len(selected_sets) > 1:
                logic_option = st.radio(
                    "集合间逻辑",
                    ["OR (匹配任意集合)", "AND (匹配所有集合)"],
                    index=0,
                    help="OR: 匹配任意一个选中的集合；AND: 必须匹配所有选中的集合"
                )
                logic = "OR" if logic_option == "OR (匹配任意集合)" else "AND"
            else:
                logic = "OR"
            
            # 显示选中的集合信息
            if selected_sets:
                st.markdown("---")
                st.markdown("**已选集合:**")
                for set_name in selected_sets.keys():
                    set_data = custom_sets.get(set_name, {})
                    keywords = set_data.get("keywords", [])
                    description = set_data.get("description", "")
                    
                    with st.expander(f"📁 {set_name}", expanded=False):
                        if description:
                            st.caption(f"描述: {description}")
                        st.write("关键词:")
                        # 显示前10个关键词
                        keywords_to_show = keywords[:10]
                        for kw in keywords_to_show:
                            st.code(kw, language=None)
                        if len(keywords) > 10:
                            st.caption(f"... 还有 {len(keywords)-10} 个关键词")

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
    
    # 获取最新一天的数据（只显示当天的数据）
    latest_data = get_latest_data(data, fixture_type)
    
    # 统计信息
    total_records = len(latest_data)
    st.info(f"今日共 {total_records} 条记录")
    
    # ========== 动态生成基础筛选器 ==========
    with st.sidebar.expander("🔍 基础筛选", expanded=True):
        st.subheader("基础筛选选项")
        
        if fixture_type in ["TIMECHARTER", "PERIOD"]:
            # TIMECHARTER 和 PERIOD 的筛选器
            col1, col2 = st.columns(2)
            
            with col1:
                if 'deliveryPort' in latest_data.columns and not latest_data['deliveryPort'].dropna().empty:
                    all_delivery_ports = sorted(latest_data['deliveryPort'].dropna().unique())
                    selected_delivery_ports = st.multiselect(
                        "Delivery Ports",
                        options=all_delivery_ports,
                        default=[],
                        help="选择要显示的交付港口，不选则显示全部"
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
                        default=[],
                        help="选择要显示的装载区域，不选则显示全部"
                    )
                else:
                    selected_load_areas = []
                    st.info("Load Areas: 无数据")
            
            col3, col4 = st.columns(2)
            
            with col3:
                if 'VESSEL TYPE' in latest_data.columns and not latest_data['VESSEL TYPE'].dropna().empty:
                    all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                    selected_vessel_types = st.multiselect(
                        "Vessel Types",
                        options=all_vessel_types,
                        default=[],
                        help="选择要显示的船舶类型，不选则显示全部"
                    )
                else:
                    selected_vessel_types = []
                    st.info("Vessel Types: 无数据")
            
            with col4:
                if 'charterer' in latest_data.columns and not latest_data['charterer'].dropna().empty:
                    all_charterers = sorted(latest_data['charterer'].dropna().unique())
                    selected_charterers = st.multiselect(
                        "Charterers",
                        options=all_charterers,
                        default=[],
                        help="选择要显示的租船人，不选则显示全部"
                    )
                else:
                    selected_charterers = []
                    st.info("Charterers: 无数据")
            
            # 第二行筛选器
            if fixture_type == "TIMECHARTER":
                col5, col6 = st.columns(2)
                
                with col5:
                    if 'via' in latest_data.columns and not latest_data['via'].dropna().empty:
                        all_via = sorted(latest_data['via'].dropna().unique())
                        selected_via = st.multiselect(
                            "Via Ports",
                            options=all_via,
                            default=[],
                            help="选择要显示的中转港口，不选则显示全部"
                        )
                    else:
                        selected_via = []
                        st.info("Via Ports: 无数据")
                
                with col6:
                    if 'redel' in latest_data.columns and not latest_data['redel'].dropna().empty:
                        all_redel = sorted(latest_data['redel'].dropna().unique())
                        selected_redel = st.multiselect(
                            "Redelivery Ports",
                            options=all_redel,
                            default=[],
                            help="选择要显示的还船港口，不选则显示全部"
                        )
                    else:
                        selected_redel = []
                        st.info("Redelivery Ports: 无数据")
            else:
                # PERIOD类型只有redel
                if 'redel' in latest_data.columns and not latest_data['redel'].dropna().empty:
                    all_redel = sorted(latest_data['redel'].dropna().unique())
                    selected_redel = st.multiselect(
                        "Redelivery Ports",
                        options=all_redel,
                        default=[],
                        help="选择要显示的还船港口，不选则显示全部"
                    )
                else:
                    selected_redel = []
        
        else:
            # VOYAGE类型的筛选器
            col1, col2 = st.columns(2)
            
            with col1:
                if 'loadArea' in latest_data.columns and not latest_data['loadArea'].dropna().empty:
                    all_load_areas = sorted(latest_data['loadArea'].dropna().unique())
                    selected_load_areas = st.multiselect(
                        "Load Areas",
                        options=all_load_areas,
                        default=[],
                        help="选择要显示的装载区域，不选则显示全部"
                    )
                else:
                    selected_load_areas = []
                    st.info("Load Areas: 无数据")
                
                if 'loadPort' in latest_data.columns and not latest_data['loadPort'].dropna().empty:
                    all_load_ports = sorted(latest_data['loadPort'].dropna().unique())
                    selected_load_ports = st.multiselect(
                        "Load Ports",
                        options=all_load_ports,
                        default=[],
                        help="选择要显示的装载港口，不选则显示全部"
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
                        default=[],
                        help="选择要显示的卸货港口，不选则显示全部"
                    )
                else:
                    selected_discharge_ports = []
                    st.info("Discharge Ports: 无数据")
                
                if 'VESSEL TYPE' in latest_data.columns and not latest_data['VESSEL TYPE'].dropna().empty:
                    all_vessel_types = sorted(latest_data['VESSEL TYPE'].dropna().unique())
                    selected_vessel_types = st.multiselect(
                        "Vessel Types",
                        options=all_vessel_types,
                        default=[],
                        help="选择要显示的船舶类型，不选则显示全部"
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
                        default=[],
                        help="选择要显示的租船人，不选则显示全部"
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
                        default=[],
                        help="选择要显示的货物尺寸，不选则显示全部"
                    )
                else:
                    selected_cargo_sizes = []
                    st.info("Cargo Sizes: 无数据")
    
    # ========== 应用基础筛选 ==========
    filtered_data = latest_data.copy()
    
    # 应用基础筛选
    if fixture_type in ["TIMECHARTER", "PERIOD"]:
        if selected_delivery_ports:
            filtered_data = filtered_data[filtered_data['deliveryPort'].isin(selected_delivery_ports) | filtered_data['deliveryPort'].isna()]
        
        if selected_load_areas:
            filtered_data = filtered_data[filtered_data['loadArea'].isin(selected_load_areas) | filtered_data['loadArea'].isna()]
        
        if selected_vessel_types:
            filtered_data = filtered_data[filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | filtered_data['VESSEL TYPE'].isna()]
        
        if selected_charterers:
            filtered_data = filtered_data[filtered_data['charterer'].isin(selected_charterers) | filtered_data['charterer'].isna()]
        
        if 'selected_via' in locals() and selected_via:
            filtered_data = filtered_data[filtered_data['via'].isin(selected_via) | filtered_data['via'].isna()]
        
        if 'selected_redel' in locals() and selected_redel:
            filtered_data = filtered_data[filtered_data['redel'].isin(selected_redel) | filtered_data['redel'].isna()]
    
    else:  # VOYAGE类型
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
    
    # ========== 应用自定义集合筛选 ==========
    if selected_sets:
        # 增加集合使用计数
        for set_name in selected_sets.keys():
            if CONFIG_MANAGER_AVAILABLE:
                increment_usage_count(set_name)
        
        # 应用自定义集合筛选
        custom_filter_mask = filtered_data.apply(
            lambda row: contains_keywords(row, fixture_type, selected_sets, logic),
            axis=1
        )
        
        custom_filtered_data = filtered_data[custom_filter_mask].copy()
        
        # 显示筛选统计
        original_count = len(filtered_data)
        custom_count = len(custom_filtered_data)
        st.success(f"**自定义集合筛选已启用** - 从 {original_count} 条记录中筛选出 {custom_count} 条匹配记录")
        
        # 使用自定义筛选后的数据
        filtered_data = custom_filtered_data
    
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
            default_columns = available_columns[:8]
        
        visible_columns = st.multiselect(
            "选择显示的列",
            options=available_columns,
            default=default_columns,
            help="选择要在表格中显示的列"
        )
        
        if visible_columns:
            display_data = filtered_data[visible_columns]
            
            # 高亮自定义集合匹配的港口
            if selected_sets:
                # 收集所有选中的关键词
                all_selected_keywords = []
                for keywords in selected_sets.values():
                    all_selected_keywords.extend(keywords)
                
                # 去重
                all_selected_keywords = list(set(all_selected_keywords))
                
                # 定义高亮函数
                def highlight_matching_ports(val):
                    if pd.isna(val):
                        return ''
                    
                    val_str = str(val).upper()
                    for keyword in all_selected_keywords:
                        if keyword.upper() in val_str:
                            # 根据匹配的集合数量决定颜色深度
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
                        styled_df[col] = styled_df[col].apply(highlight_matching_ports)
                
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
            col1, col2 = st.columns(2)
            with col1:
                st.metric("筛选后记录数", len(filtered_data))
            with col2:
                if len(filtered_data) > 0 and len(latest_data) > 0:
                    percentage = (len(filtered_data) / len(latest_data)) * 100
                    st.metric("占今日数据比例", f"{percentage:.1f}%")
            
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
    
    # 显示自定义集合使用情况
    if selected_sets and 'filtered_data' in locals():
        original_count = len(latest_data) if not latest_data.empty else 0
        filtered_count = len(filtered_data)
        if original_count > 0:
            filter_percentage = (filtered_count / original_count) * 100
            st.sidebar.write(f"**集合筛选后:** {filtered_count} 条 ({filter_percentage:.1f}%)")
        
        # 显示使用的集合
        st.sidebar.write(f"**使用集合:** {len(selected_sets)} 个")
        for set_name in selected_sets.keys():
            st.sidebar.write(f"  • {set_name}")
else:
    st.sidebar.warning(f"**{fixture_type}**: 无数据")

# ==================== 数据状态详情 ====================
with st.expander("📋 查看所有数据状态详情"):
    st.write("**数据加载状态详情:**")
    
    for name, data in data_mapping:
        if data is None:
            st.write(f"❌ **{name}**: 未加载")
        elif hasattr(data, 'empty') and data.empty:
            st.write(f"⚠️ **{name}**: 已加载但为空")
        else:
            latest_date = data.index.max() if not data.empty else "N/A"
            st.write(f"✅ **{name}**: {len(data)} 条记录，最新日期: {latest_date}")

# ==================== 自定义集合使用说明 ====================
with st.expander("🗂️ 自定义集合使用说明"):
    st.markdown("""
    ### 什么是自定义筛选集合？
    
    自定义筛选集合是您创建的港口关键词分组，可以帮助您快速筛选感兴趣的数据。
    
    ### 如何使用？
    
    1. **选择集合**：在左侧边栏的"自定义筛选集合"部分，勾选您想要使用的集合
    2. **选择逻辑**：
       - **OR逻辑**：匹配任意一个选中的集合
       - **AND逻辑**：必须匹配所有选中的集合
    3. **查看结果**：表格中匹配的港口会被高亮显示
    
    ### 示例场景：
    
    - **单集合筛选**：只勾选"Australia"集合，查看所有Australia相关的租约
    - **多集合OR筛选**：勾选"Australia"和"ECSA"集合，查看这两个地区中任意一个相关的租约
    - **多集合AND筛选**：勾选"USG"和"VCG"集合，查看同时涉及美国墨西哥湾和谷物贸易的租约
    
    ### 管理集合：
    
    要创建、编辑或删除集合，请访问 **Data Manager** 页面。
    
    ### 当前可用集合：
    """)
    
    if CONFIG_MANAGER_AVAILABLE:
        custom_sets = get_custom_sets()
        if custom_sets:
            for set_name, set_data in custom_sets.items():
                keywords = set_data.get("keywords", [])
                description = set_data.get("description", "")
                usage_count = set_data.get("usage_count", 0)
                
                st.markdown(f"**{set_name}**")
                if description:
                    st.caption(f"描述: {description}")
                st.caption(f"关键词数量: {len(keywords)} | 使用次数: {usage_count}")
                
                # 显示前5个关键词
                if keywords:
                    keywords_preview = keywords[:5]
                    preview_text = ", ".join(keywords_preview)
                    if len(keywords) > 5:
                        preview_text += f" ... 还有 {len(keywords)-5} 个"
                    st.write(f"`{preview_text}`")
                st.markdown("---")
        else:
            st.info("还没有创建任何自定义集合")
    else:
        st.error("配置管理模块不可用")

# 添加导航到Data Manager的链接
st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ 集合管理")
if st.sidebar.button("⚙️ 前往 Data Manager"):
    st.switch_page("pages/2_⚙️_Data_Manager.py")
