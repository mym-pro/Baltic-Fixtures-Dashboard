"""配置管理模块
负责加载、保存和管理用户的自定义筛选集合配置
使用GitHub作为存储后端
"""

import json
import base64
import os
from datetime import datetime
import streamlit as st
import requests

class GitHubConfigManager:
    """GitHub配置管理器 - 将配置存储在GitHub仓库中"""
    
    def __init__(self, config_file="custom_filters_config.json"):
        self.config_file = config_file
        
        # 尝试从环境变量或Streamlit secrets获取GitHub配置
        try:
            self.github_owner = st.secrets.get("GITHUB_OWNER", os.environ.get("GITHUB_OWNER", ""))
            self.github_repo = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))
            self.github_branch = st.secrets.get("GITHUB_BRANCH", os.environ.get("GITHUB_BRANCH", "main"))
            self.github_token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
            
            if not all([self.github_owner, self.github_repo, self.github_token]):
                st.warning("GitHub配置不完整，将使用Session State临时存储")
                self.use_github = False
            else:
                self.use_github = True
                # 构建GitHub API URL
                self.api_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/contents/{self.config_file}"
                # 构建Raw URL（用于读取）
                self.raw_url = f"https://raw.githubusercontent.com/{self.github_owner}/{self.github_repo}/{self.github_branch}/{self.config_file}"
                
        except Exception as e:
            st.warning(f"GitHub配置获取失败: {e}，将使用Session State临时存储")
            self.use_github = False
        
        self.default_config = {
            "custom_sets": {
                "Australia": {
                    "keywords": [
                        "AUSTRALIA", "AUS", "WESTERN AUSTRALIA", "WA",
                        "QUEENSLAND", "QLD", "NEW SOUTH WALES", "NSW",
                        "VICTORIA", "VIC", "SOUTH AUSTRALIA", "SA",
                        "TASMANIA", "TAS", "NORTHERN TERRITORY", "NT",
                        "SYDNEY", "MELBOURNE", "BRISBANE", "PERTH",
                        "ADELAIDE", "DARWIN", "HOBART", "NEWCASTLE",
                        "FREMANTLE", "GEELONG", "PORT KEMBLA",
                        "TOWNSVILLE", "CAIRNS", "GLADSTONE", "MACKAY",
                        "BUNBURY", "ESPERANCE", "ALBANY", "PORT LINCOLN",
                        "PORT HEDLAND", "DAMPIER", "HAY POINT", "ABBOT POINT",
                        "PORT WALCOTT", "CAPE LAMBERT", "PORT ALMA",
                        "PORT BOTANY", "PORT OF BRISBANE", "PORT OF MELBOURNE",
                        "PORT OF ADELAIDE", "PORT OF FREMANTLE",
                        "WEIPA", "GOVE", "KARRATHA", "GERALDTON",
                        "BROOME", "PORTLAND", "BURNIE", "DEVONPORT",
                        "PORT PIRIE", "WHYALLA", "PORT GILES"
                    ],
                    "description": "澳大利亚港口集合",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "is_template": True,
                    "usage_count": 0
                },
                "ECSA": {
                    "keywords": [
                        "ECSA", "EAST COAST SOUTH AMERICA", "BRAZIL", 
                        "ARGENTINA", "URUGUAY", "SANTOS", "TUBARAO", 
                        "SEPETIBA", "ITAGUAI", "PARANAGUA", "RIO GRANDE"
                    ],
                    "description": "东海岸南美洲港口集合",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "is_template": True,
                    "usage_count": 0
                },
                "USG": {
                    "keywords": [
                        "US GULF", "USGC", "GULF COAST", "HOUSTON", 
                        "NEW ORLEANS", "CORPUS CHRISTI", "BEAUMONT",
                        "LAKE CHARLES", "MOBILE", "PASCAGOULA"
                    ],
                    "description": "美国墨西哥湾港口集合",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "is_template": True,
                    "usage_count": 0
                },
                "FAR_EAST": {
                    "keywords": [
                        "CHINA", "JAPAN", "KOREA", "SINGAPORE", 
                        "TAIWAN", "HONG KONG", "SHANGHAI", "NINGBO",
                        "QINGDAO", "BUSAN", "YOKOHAMA", "KAOHSIUNG"
                    ],
                    "description": "远东地区港口集合",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "is_template": True,
                    "usage_count": 0
                }
            },
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
    
    def load_config(self):
        """从GitHub或Session State加载配置"""
        if self.use_github:
            try:
                # 从GitHub加载配置
                headers = {}
                if self.github_token:
                    headers['Authorization'] = f"token {self.github_token}"
                
                # 尝试从GitHub获取配置
                response = requests.get(self.api_url, headers=headers)
                
                if response.status_code == 200:
                    # 文件存在，解码内容
                    content_data = response.json()
                    content = base64.b64decode(content_data['content']).decode('utf-8')
                    config = json.loads(content)
                    
                    # 验证配置文件结构
                    if self._validate_config(config):
                        return config
                    else:
                        st.warning("GitHub上的配置文件结构无效，将使用默认配置")
                        return self._create_default_github_config()
                else:
                    # 文件不存在，创建默认配置
                    st.info("GitHub上未找到配置文件，将创建默认配置")
                    return self._create_default_github_config()
                    
            except Exception as e:
                st.warning(f"从GitHub加载配置失败 ({e})，将使用Session State配置")
                return self._load_from_session()
        else:
            # 不使用GitHub，从Session State加载
            return self._load_from_session()
    
    def _load_from_session(self):
        """从Session State加载配置"""
        if 'app_config' in st.session_state:
            return st.session_state.app_config
        else:
            # 初始化Session State配置
            self._save_to_session(self.default_config.copy())
            return st.session_state.app_config
    
    def _save_to_session(self, config):
        """保存配置到Session State"""
        st.session_state.app_config = config
    
    def _create_default_github_config(self):
        """创建默认配置并保存到GitHub"""
        default_config = self.default_config.copy()
        if self.use_github:
            try:
                self.save_config(default_config)
                st.success("✅ 默认配置已创建并保存到GitHub")
            except Exception as e:
                st.warning(f"保存默认配置到GitHub失败: {e}")
                st.info("将使用Session State临时存储配置")
        return default_config
    
    def _validate_config(self, config):
        """验证配置文件的完整性"""
        try:
            # 检查必需字段
            if "custom_sets" not in config:
                return False
            
            # 检查每个集合的结构
            for set_name, set_data in config.get("custom_sets", {}).items():
                if not isinstance(set_data, dict):
                    return False
                if "keywords" not in set_data or not isinstance(set_data["keywords"], list):
                    return False
            
            return True
        except:
            return False
    
    def save_config(self, config):
        """保存配置到GitHub或Session State"""
        # 更新最后修改时间
        config["last_modified"] = datetime.now().isoformat()
        
        if self.use_github:
            try:
                # 获取当前文件的SHA（如果存在）
                sha = None
                try:
                    headers = {'Authorization': f'token {self.github_token}'}
                    response = requests.get(self.api_url, headers=headers)
                    if response.status_code == 200:
                        sha = response.json()['sha']
                except:
                    pass  # 文件不存在，sha为None
                
                # 准备内容
                content = json.dumps(config, ensure_ascii=False, indent=2)
                content_bytes = content.encode('utf-8')
                content_b64 = base64.b64encode(content_bytes).decode('utf-8')
                
                # 准备请求数据
                data = {
                    "message": f"Update {self.config_file} via Baltic Dashboard",
                    "content": content_b64,
                    "branch": self.github_branch
                }
                if sha:
                    data["sha"] = sha
                
                # 发送请求到GitHub API
                headers = {
                    'Authorization': f'token {self.github_token}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.put(self.api_url, headers=headers, json=data)
                response.raise_for_status()
                
                # 同时更新Session State
                self._save_to_session(config)
                
                return True
            except Exception as e:
                st.error(f"保存配置到GitHub失败: {e}")
                # 回退到Session State
                self._save_to_session(config)
                return False
        else:
            # 保存到Session State
            self._save_to_session(config)
            return True
    
    def get_all_sets(self):
        """获取所有自定义集合"""
        config = self.load_config()
        return config.get("custom_sets", {})
    
    def get_set(self, set_name):
        """获取特定集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        return sets.get(set_name.upper())
    
    def create_set(self, set_name, keywords, description=""):
        """创建新的自定义集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        set_name_upper = set_name.upper()
        
        if set_name_upper in sets:
            return False, f"集合 '{set_name}' 已存在"
        
        # 清理关键词
        cleaned_keywords = [str(kw).strip().upper() for kw in keywords if str(kw).strip()]
        
        sets[set_name_upper] = {
            "keywords": cleaned_keywords,
            "description": description.strip(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_template": False,
            "usage_count": 0
        }
        
        config["custom_sets"] = sets
        
        if self.save_config(config):
            return True, f"集合 '{set_name}' 创建成功"
        else:
            return False, "集合创建失败"
    
    def update_set(self, set_name, keywords=None, description=None):
        """更新现有集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        set_name_upper = set_name.upper()
        
        if set_name_upper not in sets:
            return False, f"集合 '{set_name}' 不存在"
        
        set_data = sets[set_name_upper]
        
        if keywords is not None:
            # 清理关键词
            cleaned_keywords = [str(kw).strip().upper() for kw in keywords if str(kw).strip()]
            set_data["keywords"] = cleaned_keywords
        
        if description is not None:
            set_data["description"] = description.strip()
        
        set_data["updated_at"] = datetime.now().isoformat()
        
        if self.save_config(config):
            return True, f"集合 '{set_name}' 更新成功"
        else:
            return False, "集合更新失败"
    
    def delete_set(self, set_name):
        """删除集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        set_name_upper = set_name.upper()
        
        if set_name_upper not in sets:
            return False, f"集合 '{set_name}' 不存在"
        
        # 不删除模板集合
        if sets[set_name_upper].get("is_template", False):
            return False, "无法删除模板集合"
        
        del sets[set_name_upper]
        config["custom_sets"] = sets
        
        if self.save_config(config):
            return True, f"集合 '{set_name}' 删除成功"
        else:
            return False, "集合删除失败"
    
    def get_templates(self):
        """获取所有模板集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        templates = {}
        for set_name, set_data in sets.items():
            if set_data.get("is_template", False):
                templates[set_name] = set_data
        
        return templates
    
    def save_as_template(self, set_name):
        """将集合保存为模板"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        set_name_upper = set_name.upper()
        
        if set_name_upper not in sets:
            return False, f"集合 '{set_name}' 不存在"
        
        sets[set_name_upper]["is_template"] = True
        
        if self.save_config(config):
            return True, "模板保存成功"
        else:
            return False, "模板保存失败"
    
    def apply_template(self, template_name, new_set_name):
        """应用模板创建新集合"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        template_name_upper = template_name.upper()
        new_set_name_upper = new_set_name.upper()
        
        if template_name_upper not in sets:
            return False, f"模板 '{template_name}' 不存在"
        
        if new_set_name_upper in sets:
            return False, f"集合 '{new_set_name}' 已存在"
        
        # 获取模板数据
        template_data = sets[template_name_upper]
        
        # 深拷贝模板数据，创建新集合
        import copy
        new_set_data = copy.deepcopy(template_data)
        new_set_data["is_template"] = False
        new_set_data["created_at"] = datetime.now().isoformat()
        new_set_data["updated_at"] = datetime.now().isoformat()
        
        sets[new_set_name_upper] = new_set_data
        
        if self.save_config(config):
            return True, f"成功应用模板创建集合 '{new_set_name}'"
        else:
            return False, "应用模板失败"
    
    def export_config(self):
        """导出配置为JSON字符串"""
        config = self.load_config()
        return json.dumps(config, ensure_ascii=False, indent=2)
    
    def import_config(self, config_data):
        """导入配置"""
        try:
            config = json.loads(config_data)
            
            # 验证导入的配置
            if not self._validate_config(config):
                return False, "导入的配置文件格式无效"
            
            # 保存配置
            if self.save_config(config):
                return True, "配置导入成功"
            else:
                return False, "配置保存失败"
        except Exception as e:
            return False, f"配置文件解析失败: {e}"
    
    def reset_to_default(self):
        """重置为默认配置"""
        if self.save_config(self.default_config.copy()):
            return True, "已重置为默认配置"
        else:
            return False, "重置配置失败"
    
    def increment_usage_count(self, set_name):
        """增加集合使用计数"""
        config = self.load_config()
        sets = config.get("custom_sets", {})
        
        set_name_upper = set_name.upper()
        
        if set_name_upper in sets:
            current_count = sets[set_name_upper].get("usage_count", 0)
            sets[set_name_upper]["usage_count"] = current_count + 1
            
            if self.save_config(config):
                return True
            else:
                return False
        return False


# 创建全局配置管理器实例
config_manager = GitHubConfigManager()

# 简化接口函数
def init_session_config():
    """初始化Session State中的配置"""
    # 加载配置到Session State
    if 'app_config' not in st.session_state:
        st.session_state.app_config = config_manager.load_config()

def get_custom_sets():
    """获取自定义筛选集合"""
    if 'app_config' in st.session_state:
        return st.session_state.app_config.get("custom_sets", {})
    return config_manager.get_all_sets()

def get_set(set_name):
    """获取特定集合"""
    return config_manager.get_set(set_name)

def get_set_keywords(set_name):
    """获取特定集合的关键词列表"""
    set_data = get_set(set_name)
    if set_data:
        return set_data.get("keywords", [])
    return []

def get_all_sets_names():
    """获取所有集合名称"""
    sets = get_custom_sets()
    return list(sets.keys())

def increment_usage_count(set_name):
    """增加集合使用计数"""
    return config_manager.increment_usage_count(set_name)

def create_set(set_name, keywords, description=""):
    """创建新集合并刷新session state"""
    success, message = config_manager.create_set(set_name, keywords, description)
    if success:
        init_session_config()  # 刷新session state
    return success, message

def update_set(set_name, keywords=None, description=None):
    """更新集合并刷新session state"""
    success, message = config_manager.update_set(set_name, keywords, description)
    if success:
        init_session_config()  # 刷新session state
    return success, message

def delete_set(set_name):
    """删除集合并刷新session state"""
    success, message = config_manager.delete_set(set_name)
    if success:
        init_session_config()  # 刷新session state
    return success, message

def get_templates():
    """获取所有模板集合"""
    return config_manager.get_templates()

def save_as_template(set_name):
    """将集合保存为模板"""
    return config_manager.save_as_template(set_name)

def apply_template(template_name, new_set_name):
    """应用模板创建新集合"""
    success, message = config_manager.apply_template(template_name, new_set_name)
    if success:
        init_session_config()  # 刷新session state
    return success, message

def export_config():
    """导出配置为JSON字符串"""
    return config_manager.export_config()

def import_config(config_data):
    """导入配置"""
    success, message = config_manager.import_config(config_data)
    if success:
        init_session_config()  # 刷新session state
    return success, message

def reset_to_default():
    """重置为默认配置"""
    success, message = config_manager.reset_to_default()
    if success:
        init_session_config()  # 刷新session state
    return success, message

def refresh_session_config():
    """刷新Session State中的配置"""
    init_session_config()

def get_github_status():
    """获取GitHub存储状态"""
    return {
        "use_github": config_manager.use_github,
        "github_owner": getattr(config_manager, 'github_owner', None),
        "github_repo": getattr(config_manager, 'github_repo', None)
    }
