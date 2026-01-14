# pages/2_⚙️_Data_Manager.py
import streamlit as st
import pandas as pd
import json
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🗂️ 自定义筛选集合管理器")

# 导入配置管理模块
try:
    from config_manager import (
        get_custom_sets, 
        get_all_sets_names,
        get_set,
        create_set,
        update_set,
        delete_set,
        get_templates,
        save_as_template,
        apply_template,
        export_config,
        import_config,
        reset_to_default,
        init_session_config
    )
    CONFIG_MANAGER_AVAILABLE = True
except ImportError as e:
    st.error(f"配置管理模块导入失败: {e}")
    CONFIG_MANAGER_AVAILABLE = False

if not CONFIG_MANAGER_AVAILABLE:
    st.error("配置管理模块不可用，请检查config_manager.py文件。")
    st.stop()

# 初始化配置
init_session_config()

# 初始化session state
if 'editing_set' not in st.session_state:
    st.session_state.editing_set = None  # 存储正在编辑的集合名称
if 'new_set_data' not in st.session_state:
    st.session_state.new_set_data = {
        'name': '',
        'keywords': '',
        'description': ''
    }

# 创建标签页
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 集合列表", 
    "✏️ 集合编辑", 
    "📚 模板库", 
    "📥 导入/导出"
])

# 辅助函数
def load_editing_set(set_name):
    """加载要编辑的集合到session state"""
    set_data = get_set(set_name)
    if set_data:
        st.session_state.editing_set = set_name
        st.session_state.new_set_data = {
            'name': set_name,
            'keywords': "\n".join(set_data.get('keywords', [])),
            'description': set_data.get('description', '')
        }

def clear_editing_set():
    """清除编辑状态"""
    st.session_state.editing_set = None
    st.session_state.new_set_data = {
        'name': '',
        'keywords': '',
        'description': ''
    }

# 标签页1：集合列表
with tab1:
    st.header("所有自定义集合")
    
    # 搜索功能
    search_query = st.text_input("搜索集合（按名称或关键词）", "")
    
    # 获取所有集合
    custom_sets = get_custom_sets()
    
    # 如果有搜索查询，进行筛选
    if search_query:
        filtered_sets = {}
        query = search_query.upper()
        for set_name, set_data in custom_sets.items():
            # 按名称搜索
            if query in set_name:
                filtered_sets[set_name] = set_data
                continue
            
            # 按描述搜索
            if query in set_data.get("description", "").upper():
                filtered_sets[set_name] = set_data
                continue
            
            # 按关键词搜索
            for keyword in set_data.get("keywords", []):
                if query in keyword:
                    filtered_sets[set_name] = set_data
                    break
    else:
        filtered_sets = custom_sets
    
    # 显示集合统计
    st.write(f"共 {len(filtered_sets)} 个集合（总计 {len(custom_sets)} 个）")
    
    if not filtered_sets:
        st.info("没有找到集合。")
    else:
        # 为每个集合创建一个可展开的卡片
        for set_name, set_data in filtered_sets.items():
            keywords = set_data.get("keywords", [])
            description = set_data.get("description", "")
            created_at = set_data.get("created_at", "")
            updated_at = set_data.get("updated_at", "")
            is_template = set_data.get("is_template", False)
            usage_count = set_data.get("usage_count", 0)
            
            with st.expander(f"{set_name} ({len(keywords)}个关键词)", expanded=False):
                col1, col2 = st.columns([3, 1])
                with col1:
                    if description:
                        st.write(f"**描述**: {description}")
                    st.write(f"**创建时间**: {created_at[:10] if created_at else 'N/A'}")
                    st.write(f"**更新时间**: {updated_at[:10] if updated_at else 'N/A'}")
                    st.write(f"**使用次数**: {usage_count}")
                    if is_template:
                        st.success("这是一个模板")
                
                with col2:
                    # 编辑按钮
                    if st.button("编辑", key=f"edit_{set_name}"):
                        load_editing_set(set_name)
                        st.rerun()
                    
                    # 删除按钮（模板不能删除）
                    if not is_template:
                        if st.button("删除", key=f"delete_{set_name}"):
                            success, message = delete_set(set_name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                # 显示关键词
                if keywords:
                    st.write("**关键词预览**:")
                    cols = st.columns(5)
                    for idx, kw in enumerate(keywords[:10]):  # 只显示前10个
                        with cols[idx % 5]:
                            st.code(kw)
                    if len(keywords) > 10:
                        st.caption(f"... 还有 {len(keywords)-10} 个关键词")
    
    # 创建新集合按钮
    st.divider()
    if st.button("➕ 创建新集合", use_container_width=True):
        clear_editing_set()
        st.rerun()

# 标签页2：集合编辑
with tab2:
    st.header("编辑集合")
    
    # 从session state获取当前编辑的集合信息
    editing_set = st.session_state.editing_set
    set_data = st.session_state.new_set_data
    
    # 如果是编辑现有集合，显示提示
    if editing_set:
        st.info(f"正在编辑集合: **{editing_set}**")
    
    # 集合名称
    new_set_name = st.text_input("集合名称", 
                                 value=set_data['name'],
                                 placeholder="请输入集合名称（如：Australia、ECSA等）")
    
    # 关键词编辑（文本区域，每行一个关键词）
    st.subheader("关键词")
    st.caption("每行输入一个关键词，将自动转换为大写")
    keywords_text = st.text_area("关键词列表", 
                                 value=set_data['keywords'],
                                 height=200,
                                 placeholder="例如：\nAUSTRALIA\nSYDNEY\nMELBOURNE\n...")
    
    # 描述
    description = st.text_area("集合描述", 
                               value=set_data['description'],
                               placeholder="请输入集合描述（可选）")
    
    # 按钮
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 保存集合", use_container_width=True):
            if not new_set_name.strip():
                st.error("集合名称不能为空")
            else:
                # 处理关键词文本
                keywords = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
                
                if not keywords:
                    st.error("关键词列表不能为空")
                else:
                    if editing_set and editing_set == new_set_name.upper():
                        # 更新现有集合
                        success, message = update_set(editing_set, keywords, description)
                    else:
                        # 创建新集合
                        success, message = create_set(new_set_name, keywords, description)
                    
                    if success:
                        st.success(message)
                        clear_editing_set()
                        st.rerun()
                    else:
                        st.error(message)
    
    with col2:
        if st.button("🗑️ 清空表单", use_container_width=True):
            clear_editing_set()
            st.rerun()
    
    with col3:
        if st.button("📤 导出为模板", use_container_width=True):
            if not new_set_name.strip():
                st.error("请先填写集合名称")
            elif not keywords_text.strip():
                st.error("关键词列表不能为空")
            else:
                # 先确保集合已保存
                keywords = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
                
                if editing_set and editing_set == new_set_name.upper():
                    # 更新现有集合
                    update_set(editing_set, keywords, description)
                    success, message = save_as_template(editing_set)
                else:
                    # 创建新集合并标记为模板
                    create_set(new_set_name, keywords, description)
                    success, message = save_as_template(new_set_name)
                
                if success:
                    st.success(message)
                    clear_editing_set()
                    st.rerun()
                else:
                    st.error(message)
    
    # 显示关键词统计
    if keywords_text.strip():
        keywords_list = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
        st.info(f"当前关键词数量: {len(keywords_list)}")

# 标签页3：模板库
with tab3:
    st.header("模板库")
    st.write("使用预定义模板快速创建集合")
    
    # 获取所有模板
    templates = get_templates()
    
    if not templates:
        st.info("没有可用的模板。")
    else:
        # 显示模板列表
        for template_name, template_data in templates.items():
            keywords = template_data.get("keywords", [])
            description = template_data.get("description", "")
            
            with st.expander(f"{template_name} ({len(keywords)}个关键词)", expanded=False):
                st.write(f"**描述**: {description}")
                
                # 预览前10个关键词
                st.write("**关键词预览**:")
                preview = ", ".join(keywords[:10])
                if len(keywords) > 10:
                    preview += f" ... 等 {len(keywords)} 个关键词"
                st.code(preview)
                
                # 应用模板按钮
                new_name = st.text_input(f"新集合名称", 
                                         value=f"My_{template_name}",
                                         key=f"new_name_{template_name}")
                
                if st.button("✅ 应用此模板", key=f"apply_{template_name}"):
                    if not new_name.strip():
                        st.error("请输入新集合名称")
                    else:
                        success, message = apply_template(template_name, new_name)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

# 标签页4：导入/导出
with tab4:
    st.header("导入/导出配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("导出配置")
        st.write("将当前所有集合配置导出为JSON文件")
        
        config_json = export_config()
        st.download_button(
            label="📥 下载配置文件",
            data=config_json,
            file_name="custom_filters_config.json",
            mime="application/json",
            use_container_width=True
        )
        
        # 显示配置预览
        with st.expander("预览配置"):
            try:
                st.json(json.loads(config_json))
            except:
                st.error("配置格式无效")
    
    with col2:
        st.subheader("导入配置")
        st.write("从JSON文件导入集合配置（将合并现有配置）")
        
        uploaded_file = st.file_uploader("选择配置文件", type=['json'])
        
        if uploaded_file is not None:
            try:
                config_data = uploaded_file.getvalue().decode("utf-8")
                st.success("✅ 配置文件解析成功")
                
                if st.button("🔄 导入配置", use_container_width=True):
                    success, message = import_config(config_data)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            except Exception as e:
                st.error(f"❌ 配置文件解析失败: {e}")
        
        st.divider()
        st.subheader("重置配置")
        st.write("⚠️ 将配置重置为默认状态（将删除所有自定义集合）")
        
        if st.button("🔄 重置为默认配置", use_container_width=True, type="secondary"):
            if st.checkbox("我确认要重置所有配置"):
                success, message = reset_to_default()
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

# 侧边栏信息
st.sidebar.title("ℹ️ 使用说明")
st.sidebar.info("""
**自定义筛选集合** 允许您创建和管理港口关键词分组，以便在数据展示页面快速筛选。

**主要功能：**
- **集合列表**：查看、搜索所有集合
- **集合编辑**：创建、编辑集合（关键词和描述）
- **模板库**：使用预定义模板快速创建集合
- **导入/导出**：备份和恢复配置

**使用流程：**
1. 在**集合列表**中查看现有集合
2. 在**集合编辑**中创建新集合或编辑现有集合
3. 在**模板库**中使用模板快速创建
4. 在**ALLFIX_PAGE**中使用集合进行筛选
""")

st.sidebar.divider()
st.sidebar.write("**当前配置统计**")
custom_sets = get_custom_sets()
if custom_sets:
    total_sets = len(custom_sets)
    total_keywords = sum(len(s.get("keywords", [])) for s in custom_sets.values())
    template_count = sum(1 for s in custom_sets.values() if s.get("is_template", False))
    
    st.sidebar.metric("集合总数", total_sets)
    st.sidebar.metric("关键词总数", total_keywords)
    st.sidebar.metric("模板数量", template_count)
else:
    st.sidebar.info("暂无配置")

# 添加返回按钮
st.sidebar.divider()
if st.sidebar.button("⬅️ 返回数据展示页面"):
    st.switch_page("pages/1_📊_ALLFIX_PAGE.py")