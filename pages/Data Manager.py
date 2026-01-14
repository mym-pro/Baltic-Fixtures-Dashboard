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
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "集合列表"
if 'editing_set_name' not in st.session_state:
    st.session_state.editing_set_name = None
if 'editing_keywords' not in st.session_state:
    st.session_state.editing_keywords = ""
if 'editing_description' not in st.session_state:
    st.session_state.editing_description = ""
if 'new_set_mode' not in st.session_state:
    st.session_state.new_set_mode = False

# 辅助函数
def load_editing_set(set_name):
    """加载要编辑的集合到session state"""
    set_data = get_set(set_name)
    if set_data:
        st.session_state.editing_set_name = set_name
        st.session_state.editing_keywords = "\n".join(set_data.get('keywords', []))
        st.session_state.editing_description = set_data.get('description', '')
        st.session_state.new_set_mode = False
        st.session_state.current_tab = "集合编辑"
        st.rerun()

def clear_editing_set():
    """清除编辑状态"""
    st.session_state.editing_set_name = None
    st.session_state.editing_keywords = ""
    st.session_state.editing_description = ""
    st.session_state.new_set_mode = False

def start_new_set():
    """开始创建新集合"""
    clear_editing_set()
    st.session_state.new_set_mode = True
    st.session_state.current_tab = "集合编辑"
    st.rerun()

# 创建标签页导航
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📋 集合列表", use_container_width=True, 
                 type="primary" if st.session_state.current_tab == "集合列表" else "secondary"):
        st.session_state.current_tab = "集合列表"
        st.rerun()

with col2:
    if st.button("✏️ 集合编辑", use_container_width=True,
                 type="primary" if st.session_state.current_tab == "集合编辑" else "secondary"):
        st.session_state.current_tab = "集合编辑"
        st.rerun()

with col3:
    if st.button("📚 模板库", use_container_width=True,
                 type="primary" if st.session_state.current_tab == "模板库" else "secondary"):
        st.session_state.current_tab = "模板库"
        st.rerun()

with col4:
    if st.button("📥 导入/导出", use_container_width=True,
                 type="primary" if st.session_state.current_tab == "导入/导出" else "secondary"):
        st.session_state.current_tab = "导入/导出"
        st.rerun()

st.markdown("---")

# ==================== 标签页1：集合列表 ====================
if st.session_state.current_tab == "集合列表":
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
                    
                    # 格式化时间显示
                    if created_at:
                        try:
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                            st.write(f"**创建时间**: {created_date}")
                        except:
                            st.write(f"**创建时间**: {created_at[:10]}")
                    
                    if updated_at:
                        try:
                            updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                            st.write(f"**更新时间**: {updated_date}")
                        except:
                            st.write(f"**更新时间**: {updated_at[:10]}")
                    
                    st.write(f"**使用次数**: {usage_count}")
                    if is_template:
                        st.success("📚 这是一个模板")
                
                with col2:
                    # 编辑按钮
                    if st.button("编辑", key=f"edit_{set_name}", use_container_width=True):
                        load_editing_set(set_name)
                    
                    # 删除按钮（模板不能删除）
                    if not is_template:
                        if st.button("删除", key=f"delete_{set_name}", use_container_width=True):
                            success, message = delete_set(set_name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    else:
                        st.button("删除", key=f"delete_disabled_{set_name}", 
                                 use_container_width=True, disabled=True)
                
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
        start_new_set()

# ==================== 标签页2：集合编辑 ====================
elif st.session_state.current_tab == "集合编辑":
    st.header("编辑集合")
    
    # 显示当前模式
    if st.session_state.new_set_mode:
        st.info("📝 创建新集合")
    elif st.session_state.editing_set_name:
        st.info(f"📝 正在编辑集合: **{st.session_state.editing_set_name}**")
    else:
        st.warning("请从集合列表中选择一个集合进行编辑，或创建新集合。")
        if st.button("返回集合列表"):
            st.session_state.current_tab = "集合列表"
            st.rerun()
        st.stop()
    
    # 集合名称
    current_name = st.session_state.editing_set_name if not st.session_state.new_set_mode else ""
    new_set_name = st.text_input(
        "集合名称 *", 
        value=current_name if not st.session_state.new_set_mode else "",
        placeholder="请输入集合名称（如：Australia、ECSA等）",
        disabled=not st.session_state.new_set_mode and st.session_state.editing_set_name is not None
    )
    
    # 关键词编辑（文本区域，每行一个关键词）
    st.subheader("关键词 *")
    st.caption("每行输入一个关键词，将自动转换为大写")
    keywords_text = st.text_area(
        "关键词列表", 
        value=st.session_state.editing_keywords,
        height=200,
        placeholder="例如：\nAUSTRALIA\nSYDNEY\nMELBOURNE\n..."
    )
    
    # 描述
    description = st.text_area(
        "集合描述", 
        value=st.session_state.editing_description,
        placeholder="请输入集合描述（可选）"
    )
    
    # 按钮
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 保存集合", use_container_width=True, type="primary"):
            if not new_set_name.strip():
                st.error("集合名称不能为空")
            else:
                # 处理关键词文本
                keywords = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
                
                if not keywords:
                    st.error("关键词列表不能为空")
                else:
                    if not st.session_state.new_set_mode and st.session_state.editing_set_name:
                        # 更新现有集合
                        success, message = update_set(st.session_state.editing_set_name, keywords, description)
                    else:
                        # 创建新集合
                        success, message = create_set(new_set_name, keywords, description)
                    
                    if success:
                        st.success(message)
                        clear_editing_set()
                        st.session_state.current_tab = "集合列表"
                        st.rerun()
                    else:
                        st.error(message)
    
    with col2:
        if st.button("🗑️ 取消编辑", use_container_width=True, type="secondary"):
            clear_editing_set()
            st.session_state.current_tab = "集合列表"
            st.rerun()
    
    with col3:
        if st.button("📤 导出为模板", use_container_width=True):
            if not new_set_name.strip():
                st.error("请先填写集合名称")
            elif not keywords_text.strip():
                st.error("关键词列表不能为空")
            else:
                # 确保集合已存在
                if not st.session_state.new_set_mode and st.session_state.editing_set_name:
                    # 更新现有集合并标记为模板
                    keywords = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
                    update_set(st.session_state.editing_set_name, keywords, description)
                    success, message = save_as_template(st.session_state.editing_set_name)
                else:
                    # 创建新集合并标记为模板
                    keywords = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
                    create_set(new_set_name, keywords, description)
                    success, message = save_as_template(new_set_name)
                
                if success:
                    st.success(message)
                    clear_editing_set()
                    st.session_state.current_tab = "集合列表"
                    st.rerun()
                else:
                    st.error(message)
    
    # 显示关键词统计
    if keywords_text.strip():
        keywords_list = [kw.strip().upper() for kw in keywords_text.split('\n') if kw.strip()]
        st.info(f"当前关键词数量: {len(keywords_list)}")
        
        # 显示重复关键词检查
        duplicates = []
        seen = set()
        for kw in keywords_list:
            if kw in seen:
                duplicates.append(kw)
            else:
                seen.add(kw)
        
        if duplicates:
            st.warning(f"发现重复关键词: {', '.join(duplicates)}")

# ==================== 标签页3：模板库 ====================
elif st.session_state.current_tab == "模板库":
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
            usage_count = template_data.get("usage_count", 0)
            
            with st.expander(f"{template_name} ({len(keywords)}个关键词)", expanded=False):
                if description:
                    st.write(f"**描述**: {description}")
                st.write(f"**使用次数**: {usage_count}")
                
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
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 应用此模板", key=f"apply_{template_name}", use_container_width=True):
                        if not new_name.strip():
                            st.error("请输入新集合名称")
                        else:
                            success, message = apply_template(template_name, new_name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                with col2:
                    if st.button("📝 编辑此模板", key=f"edit_template_{template_name}", use_container_width=True):
                        load_editing_set(template_name)

# ==================== 标签页4：导入/导出 ====================
elif st.session_state.current_tab == "导入/导出":
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
        
        uploaded_file = st.file_uploader("选择配置文件", type=['json'], label_visibility="collapsed")
        
        if uploaded_file is not None:
            try:
                config_data = uploaded_file.getvalue().decode("utf-8")
                st.success("✅ 配置文件解析成功")
                
                # 显示导入预览
                with st.expander("预览导入内容"):
                    try:
                        preview_config = json.loads(config_data)
                        if "custom_sets" in preview_config:
                            set_count = len(preview_config["custom_sets"])
                            st.write(f"包含 {set_count} 个集合")
                        st.json(preview_config)
                    except:
                        st.error("无法预览配置")
                
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
            with st.expander("确认重置"):
                st.warning("""
                **警告：此操作不可撤销！**
                
                将会：
                - 删除所有自定义集合
                - 恢复为默认模板集合
                - 清除所有使用统计
                """)
                
                confirm_text = st.text_input("请输入 'RESET' 确认重置:")
                
                if st.button("确认重置", type="primary"):
                    if confirm_text == "RESET":
                        success, message = reset_to_default()
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("请输入正确的确认文本")

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
