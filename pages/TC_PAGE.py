"""
新.FIXTURE_PAGE.TC_PAGE 的 Docstring
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
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(layout="wide", page_title="TC Historical Data")
st.title('⏳ TIMECHARTER Historical Data')
st.markdown("""
### TC历史数据查询
基于本地保存的历史数据进行查询和分析
""")

# ==================== Australia港口识别函数 ====================
def is_australian_port(port_name):
    """检查港口是否为Australia相关港口"""
    if pd.isna(port_name):
        return False
    
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
    
    port_str = str(port_name).upper()
    
    for keyword in australian_keywords:
        if keyword in port_str:
            return True
    
    return False

def contains_australian_info(row):
    """检查一行数据是否包含Australia相关信息"""
    fields_to_check = ['deliveryPort', 'loadArea', 'via', 'redel']
    for field in fields_to_check:
        if field in row and is_australian_port(row[field]):
            return True
    return False

# ==================== 数据加载 ====================
@st.cache_data(ttl=300)  # 缓存5分钟
def load_tc_data_from_session():
    """从session_state加载TC数据"""
    if 'tc_spot' not in st.session_state:
        return None
    
    data = st.session_state['tc_spot']
    
    if data is None:
        return None
    
    # 确保数据是DataFrame并且有正确的列
    if isinstance(data, pd.DataFrame) and not data.empty:
        # 确保数据按日期倒序排列（最新在前）
        data = data.sort_index(ascending=False)
        
        # 确保有VESSEL TYPE列
        if 'VESSEL TYPE' not in data.columns:
            # 如果数据中没有VESSEL TYPE列，我们可以尝试添加
            from datetime import date
            import re
            
            # 这里需要从你的数据处理页面导入add_vessel_type函数
            # 但由于是单独页面，我们在这里定义一个简化版本
            def add_vessel_type_simple(df):
                if df is None or df.empty:
                    return df
                
                df = df.copy()
                
                if 'dwt' not in df.columns:
                    df['VESSEL TYPE'] = None
                    return df
                
                def parse_dwt(x):
                    if pd.isna(x):
                        return None
                    try:
                        x_str = str(x).replace(',', '').strip()
                        match = re.search(r'(\d+)', x_str)
                        if match:
                            return int(match.group(1))
                        return None
                    except:
                        return None
                
                df['dwt_numeric'] = df['dwt'].apply(parse_dwt)
                
                def determine_vessel_type(dwt_val):
                    if pd.isna(dwt_val):
                        return None
                    
                    try:
                        dwt_num = float(dwt_val)
                        if dwt_num > 100000:
                            return 'CAPE/VLOC'
                        elif dwt_num > 80000 and dwt_num < 100000:
                            return 'KMX'
                        elif dwt_num >= 65000 and dwt_num <= 80000:
                            return 'PMX'
                        elif dwt_num < 65000:
                            return 'SMX/UMX/HANDY'
                        else:
                            return None
                    except:
                        return None
                
                df['VESSEL TYPE'] = df['dwt_numeric'].apply(determine_vessel_type)
                
                if 'dwt_numeric' in df.columns:
                    df = df.drop(columns=['dwt_numeric'])
                
                return df
            
            data = add_vessel_type_simple(data)
        
        return data
    
    return None

# ==================== 页面主逻辑 ====================
st.sidebar.title("📅 时间范围筛选")

# 尝试从session_state加载数据
tc_data = load_tc_data_from_session()

if tc_data is None or tc_data.empty:
    st.error("⚠️ TC数据未加载")
    st.markdown("""
    **请先返回数据处理页面加载数据：**
    1. 前往 **数据处理页面**
    2. 点击 **Update Data** 按钮
    3. 等待数据加载完成
    4. 返回此页面查看历史数据
    """)
    
    # 尝试从文件直接加载作为备用
    try:
        if os.path.exists('timecharter.csv'):
            tc_data = pd.read_csv('timecharter.csv', parse_dates=['date'])
            tc_data.set_index('date', inplace=True)
            tc_data = tc_data.sort_index(ascending=False)
            st.session_state['tc_spot'] = tc_data
            st.success(f"✅ 已从文件加载 {len(tc_data)} 条历史记录")
            # 重新加载数据
            tc_data = load_tc_data_from_session()
        else:
            st.warning("未找到历史数据文件，请先运行数据处理页面")
            st.stop()
    except Exception as e:
        st.error(f"加载数据时出错: {e}")
        st.stop()

# 显示数据基本信息
if tc_data is not None and not tc_data.empty:
    latest_date = tc_data.index.max()
    earliest_date = tc_data.index.min()
    total_records = len(tc_data)

    st.sidebar.info(f"""
    **数据概览:**
    - 最早日期: {earliest_date.strftime('%Y-%m-%d')}
    - 最新日期: {latest_date.strftime('%Y-%m-%d')}
    - 总记录数: {total_records:,}
    - 数据来源: session_state
    """)

    # ==================== 时间范围选择 ====================
    time_period = st.sidebar.selectbox(
        "选择时间范围",
        ["最近7天", "最近14天", "最近20天", "最近1个月", "最近2个月", "最近3个月", "最近6个月", "全部数据"],
        index=2  # 默认选择最近20天
    )

    # 计算开始日期
    end_date = pd.to_datetime('today')
    if time_period == "最近7天":
        start_date = end_date - timedelta(days=7)
    elif time_period == "最近14天":
        start_date = end_date - timedelta(days=14)
    elif time_period == "最近20天":
        start_date = end_date - timedelta(days=20)
    elif time_period == "最近1个月":
        start_date = end_date - timedelta(days=30)
    elif time_period == "最近2个月":
        start_date = end_date - timedelta(days=60)
    elif time_period == "最近3个月":
        start_date = end_date - timedelta(days=90)
    elif time_period == "最近6个月":
        start_date = end_date - timedelta(days=180)
    else:  # 全部数据
        start_date = earliest_date

    # 筛选时间范围内的数据
    time_filtered_data = tc_data[(tc_data.index >= start_date) & (tc_data.index <= end_date)].copy()

    st.sidebar.success(f"**{time_period}** 内共有 **{len(time_filtered_data)}** 条记录")

    # ==================== 数据筛选器 ====================
    st.sidebar.markdown("---")
    st.sidebar.title("🔍 数据筛选")

    # Australia筛选
    show_australia_only = st.sidebar.checkbox("🇦🇺 仅显示Australia相关港口", value=False)

    if show_australia_only:
        australia_mask = time_filtered_data.apply(contains_australian_info, axis=1)
        time_filtered_data = time_filtered_data[australia_mask]
        st.sidebar.info(f"Australia相关记录: {len(time_filtered_data)} 条")

    # 其他筛选器
    st.sidebar.markdown("### 港口筛选")

    if not time_filtered_data.empty:
        # deliveryPort 筛选
        if 'deliveryPort' in time_filtered_data.columns:
            all_delivery_ports = sorted(time_filtered_data['deliveryPort'].dropna().unique().tolist())
            if all_delivery_ports:
                selected_delivery = st.sidebar.multiselect(
                    "Delivery Port",
                    options=all_delivery_ports,
                    default=all_delivery_ports[:5] if len(all_delivery_ports) > 5 else all_delivery_ports
                )
                
                if selected_delivery:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['deliveryPort'].isin(selected_delivery) | 
                        time_filtered_data['deliveryPort'].isna()
                    ]
        
        # loadArea 筛选
        if 'loadArea' in time_filtered_data.columns:
            all_load_areas = sorted(time_filtered_data['loadArea'].dropna().unique().tolist())
            if all_load_areas:
                selected_load_areas = st.sidebar.multiselect(
                    "Load Area",
                    options=all_load_areas,
                    default=all_load_areas[:5] if len(all_load_areas) > 5 else all_load_areas
                )
                
                if selected_load_areas:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['loadArea'].isin(selected_load_areas) | 
                        time_filtered_data['loadArea'].isna()
                    ]
        
        # via 筛选
        if 'via' in time_filtered_data.columns:
            all_via = sorted(time_filtered_data['via'].dropna().unique().tolist())
            if all_via:
                selected_via = st.sidebar.multiselect(
                    "Via Port",
                    options=all_via,
                    default=all_via[:5] if len(all_via) > 5 else all_via
                )
                
                if selected_via:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['via'].isin(selected_via) | 
                        time_filtered_data['via'].isna()
                    ]
        
        # redel 筛选
        if 'redel' in time_filtered_data.columns:
            all_redel = sorted(time_filtered_data['redel'].dropna().unique().tolist())
            if all_redel:
                selected_redel = st.sidebar.multiselect(
                    "Redelivery Port",
                    options=all_redel,
                    default=all_redel[:5] if len(all_redel) > 5 else all_redel
                )
                
                if selected_redel:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['redel'].isin(selected_redel) | 
                        time_filtered_data['redel'].isna()
                    ]
        
        # VESSEL TYPE 筛选
        if 'VESSEL TYPE' in time_filtered_data.columns:
            all_vessel_types = sorted(time_filtered_data['VESSEL TYPE'].dropna().unique().tolist())
            if all_vessel_types:
                selected_vessel_types = st.sidebar.multiselect(
                    "Vessel Type",
                    options=all_vessel_types,
                    default=all_vessel_types
                )
                
                if selected_vessel_types:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['VESSEL TYPE'].isin(selected_vessel_types) | 
                        time_filtered_data['VESSEL TYPE'].isna()
                    ]
        
        # charterer 筛选
        if 'charterer' in time_filtered_data.columns:
            all_charterers = sorted(time_filtered_data['charterer'].dropna().unique().tolist())
            if all_charterers:
                selected_charterers = st.sidebar.multiselect(
                    "Charterer",
                    options=all_charterers,
                    default=all_charterers[:5] if len(all_charterers) > 5 else all_charterers
                )
                
                if selected_charterers:
                    time_filtered_data = time_filtered_data[
                        time_filtered_data['charterer'].isin(selected_charterers) | 
                        time_filtered_data['charterer'].isna()
                    ]

    # ==================== 主显示区域 ====================
    # 显示统计信息
    if not time_filtered_data.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("时间范围", time_period)
        with col2:
            st.metric("筛选后记录数", len(time_filtered_data))
        with col3:
            st.metric("日期范围", f"{time_filtered_data.index.min().strftime('%m-%d')} 至 {time_filtered_data.index.max().strftime('%m-%d')}")
        with col4:
            if show_australia_only:
                st.metric("筛选模式", "Australia")
            else:
                st.metric("筛选模式", "全部港口")

        st.markdown("---")

        # 数据可视化 - 按日期统计
        st.subheader("📈 数据趋势")
        
        # 按日期统计记录数
        daily_counts = time_filtered_data.groupby(time_filtered_data.index.date).size()
        
        if len(daily_counts) > 1:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # 创建折线图
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=list(daily_counts.index),
                    y=daily_counts.values,
                    mode='lines+markers',
                    name='每日记录数',
                    line=dict(color='#1E88E5', width=2),
                    marker=dict(size=6)
                ))
                
                fig1.update_layout(
                    title=f"{time_period} TC记录趋势",
                    xaxis_title="日期",
                    yaxis_title="记录数",
                    height=300,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # 显示统计摘要
                st.markdown("#### 统计摘要")
                st.write(f"**平均每日:** {daily_counts.mean():.1f}")
                st.write(f"**最高单日:** {daily_counts.max()}")
                st.write(f"**最低单日:** {daily_counts.min()}")
                st.write(f"**总天数:** {len(daily_counts)}")
        else:
            st.info("数据时间跨度不足，无法显示趋势图")

        # 船舶类型分布
        if 'VESSEL TYPE' in time_filtered_data.columns and time_filtered_data['VESSEL TYPE'].notna().any():
            vessel_counts = time_filtered_data['VESSEL TYPE'].value_counts()
            
            if len(vessel_counts) > 0:
                st.subheader("🚢 船舶类型分布")
                
                col1, col2 = st.columns([2, 3])
                
                with col1:
                    for vessel_type, count in vessel_counts.items():
                        if pd.isna(vessel_type):
                            continue
                        percentage = (count / len(time_filtered_data)) * 100
                        st.write(f"**{vessel_type}:** {count} 条 ({percentage:.1f}%)")
                
                with col2:
                    if len(vessel_counts) > 1:
                        fig2 = px.pie(
                            values=vessel_counts.values,
                            names=vessel_counts.index,
                            title="船舶类型分布",
                            height=300
                        )
                        st.plotly_chart(fig2, use_container_width=True)

        # 热门港口分析
        st.subheader("🌍 热门港口")
        
        port_columns = ['deliveryPort', 'loadArea', 'via', 'redel']
        port_data = {}
        
        for col in port_columns:
            if col in time_filtered_data.columns:
                port_counts = time_filtered_data[col].value_counts().head(5)  # 取前5
                if not port_counts.empty:
                    port_data[col] = port_counts
        
        if port_data:
            # 显示港口热度表格
            port_dfs = []
            for col_name, counts in port_data.items():
                temp_df = pd.DataFrame({
                    '港口类型': col_name,
                    '港口名称': counts.index,
                    '出现次数': counts.values,
                    '占比(%)': (counts.values / len(time_filtered_data) * 100).round(1)
                })
                port_dfs.append(temp_df)
            
            if port_dfs:
                combined_port_df = pd.concat(port_dfs, ignore_index=True)
                st.dataframe(
                    combined_port_df,
                    use_container_width=True,
                    height=200
                )

        # ==================== 详细数据表格 ====================
        st.markdown("---")
        st.subheader("📋 详细数据")
        
        # 列选择器
        available_columns = time_filtered_data.columns.tolist()
        
        # TC推荐显示的列
        tc_columns = [
            'shipName', 'dwt', 'VESSEL TYPE', 'deliveryPort', 
            'loadArea', 'via', 'redel', 'hire', 'charterer', 
            'comment', 'buildYear', 'freeText'
        ]
        
        # 确保推荐的列都存在
        default_columns = [col for col in tc_columns if col in available_columns]
        
        # 如果没有默认列，使用所有可用列
        if not default_columns:
            default_columns = available_columns[:10]
        
        visible_columns = st.multiselect(
            "选择要显示的列",
            options=available_columns,
            default=default_columns
        )
        
        if visible_columns:
            # 准备显示数据
            display_data = time_filtered_data[visible_columns].copy()
            
            # 添加日期列（索引）
            display_data = display_data.reset_index()
            
            # 高亮Australia相关港口
            if show_australia_only:
                # 对Australia港口进行高亮
                def highlight_australian(val):
                    if pd.isna(val):
                        return ''
                    if is_australian_port(val):
                        return f'<span style="background-color: #FFE5B4; font-weight: bold;">{val}</span>'
                    return val
                
                # 应用高亮到港口相关列
                port_columns_to_highlight = ['deliveryPort', 'loadArea', 'via', 'redel']
                for col in port_columns_to_highlight:
                    if col in display_data.columns:
                        display_data[col] = display_data[col].apply(highlight_australian)
                
                # 显示高亮后的表格
                st.markdown(display_data.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                # 普通显示
                st.dataframe(
                    display_data,
                    use_container_width=True,
                    height=400
                )
            
            # 提供下载选项
            st.markdown("---")
            st.subheader("📥 数据导出")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 下载CSV
                csv = display_data.to_csv(index=False)
                st.download_button(
                    label="下载CSV格式",
                    data=csv,
                    file_name=f"tc_historical_{time_period}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    help="下载为CSV文件，可用Excel打开"
                )
            
            with col2:
                # 下载Excel（需要openpyxl）
                try:
                    import openpyxl
                    
                    @st.cache_data
                    def convert_to_excel(df):
                        # 使用BytesIO避免创建临时文件
                        import io
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='TC_Data')
                        return output.getvalue()
                    
                    excel_data = convert_to_excel(display_data)
                    st.download_button(
                        label="下载Excel格式",
                        data=excel_data,
                        file_name=f"tc_historical_{time_period}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="下载为Excel文件"
                    )
                except ImportError:
                    st.info("如需Excel导出功能，请安装openpyxl: `pip install openpyxl`")
        else:
            st.warning("请选择至少一列进行显示")
    else:
        st.warning("没有符合筛选条件的数据")

    # ==================== 底部信息 ====================
    st.markdown("---")
    st.markdown("""
    ### 📊 使用说明

    **数据来源：**
    - 所有数据来自 `st.session_state['tc_spot']`
    - 该数据在 **数据处理页面** 更新时自动加载
    - 数据按日期倒序排列，最新记录显示在最前面

    **筛选功能：**
    1. **时间范围**: 选择要查看的时间段（7天到6个月）
    2. **Australia筛选**: 勾选仅显示Australia相关港口的记录
    3. **港口筛选**: 可以按deliveryPort, loadArea, via, redel筛选
    4. **船舶类型筛选**: 可以按VESSEL TYPE筛选
    5. **数据可视化**: 查看数据趋势和分布
    6. **数据导出**: 下载筛选后的数据为CSV或Excel格式

    **数据更新：**
    - 返回 **数据处理页面** 点击 **Update Data** 按钮
    - 系统会自动获取最新数据并追加到历史文件中
    - 建议每周更新一次以保持数据最新

    **注意事项：**
    - 所有筛选都在本地进行，不会影响原始数据文件
    - 如果数据量很大，筛选可能需要几秒钟时间
    - 确保有足够的内存处理历史数据
    """)

    # 添加刷新按钮
    if st.button("🔄 刷新页面"):
        st.cache_data.clear()
        st.rerun()

else:
    st.error("没有可用的TC数据")