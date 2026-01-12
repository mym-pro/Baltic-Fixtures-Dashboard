#设置页面
import streamlit as st
st.set_page_config(layout="wide") #宽屏模式
#st.text('updated') #st.text就是直接在页面上显示文本
st.title('Baltic Fixture Dashboard')

# 依赖项
import warnings; warnings.simplefilter('ignore') #把 Python 的所有警告（如链式赋值、过期 API）静默掉，让控制台干净，调试阶段可注释掉以便发现潜在问题。
import pandas as pd
import time
import re
import numpy as np
from datetime import date
from calendar import monthrange
from pandas.tseries.offsets import BDay # Bday是工作日
import requests
import os
from pathlib import Path
import ftplib #波罗的海官网/部分经纪行仍提供 FTP 下载（txt/csv 格式），用来自动抓历史指数。
import random  # 用于随机延迟，避免固定模式被识别为爬虫
import base64
from io import BytesIO
from github import Github

pd.set_option('display.max_rows',None)
pd.set_option('display.max_columns',None)
#让 DataFrame 不管多少行都 全部打印出来，不再出现中间省略号，这两行只是方便 开发调试阶段 在控制台里一眼看全表；上线后可以保留，也可以删掉，对最终用户界面没有任何影响。

# GitHub配置 - 从streamlit secrets获取
try:
    GITHUB_TOKEN = st.secrets.github.token
    REPO_NAME = st.secrets.github.repo
    ENABLE_GITHUB_SAVE = True
    st.text("GitHub配置已加载")
except Exception as e:
    GITHUB_TOKEN = None
    REPO_NAME = None
    ENABLE_GITHUB_SAVE = False
    st.warning("未配置GitHub保存，请配置secrets.toml文件")

# GitHub数据管理器类
class GitHubFixtureManager:
    def __init__(self, repo_name: str, github_token: str):
        self.repo_name = repo_name
        self.github_token = github_token
        self.g = Github(github_token)
        self.repo = self.g.get_repo(repo_name)
        self.base_path = 'fixture_data'
    
    def save_fixture_data(self, df: pd.DataFrame, file_name: str, data_type: str):
        """保存fixture数据到GitHub"""
        if df is None or df.empty:
            st.warning(f"{data_type}数据为空，跳过保存")
            return False
        
        try:
            # 准备数据 - 确保有date列
            if df.index.name == 'date':
                df = df.reset_index()
            elif 'date' not in df.columns:
                st.error(f"{data_type}数据缺少date列，无法保存")
                return False
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # 将DataFrame转换为CSV字符串
            csv_data = df.to_csv(index=False)
            
            # 完整的文件路径
            full_path = f"{self.base_path}/{file_name}"
            
            # 尝试获取现有文件
            try:
                contents = self.repo.get_contents(full_path)
                # 文件存在，更新
                self.repo.update_file(
                    full_path,
                    f"更新{data_type}数据 - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
                    csv_data,
                    contents.sha
                )
                st.success(f"{data_type}数据已更新到GitHub: {full_path}")
                return True
            except Exception as e:
                # 文件不存在，创建新文件
                self.repo.create_file(
                    full_path,
                    f"创建{data_type}数据 - {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
                    csv_data
                )
                st.success(f"{data_type}数据已创建到GitHub: {full_path}")
                return True
                
        except Exception as e:
            st.error(f"保存{data_type}数据到GitHub失败: {str(e)}")
            return False
    
    def load_fixture_data(self, file_name: str):
        """从GitHub加载fixture数据"""
        try:
            full_path = f"{self.base_path}/{file_name}"
            contents = self.repo.get_contents(full_path)
            csv_data = base64.b64decode(contents.content).decode('utf-8')
            df = pd.read_csv(BytesIO(csv_data.encode('utf-8')))
            
            # 转换日期列
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
        except Exception as e:
            st.warning(f"从GitHub加载{file_name}失败: {str(e)}")
            return None
    
    def file_exists(self, file_name: str):
        """检查文件是否存在"""
        try:
            full_path = f"{self.base_path}/{file_name}"
            self.repo.get_contents(full_path)
            return True
        except:
            return False

# 创建GitHub管理器
github_manager = None
if ENABLE_GITHUB_SAVE and GITHUB_TOKEN and REPO_NAME:
    try:
        github_manager = GitHubFixtureManager(REPO_NAME, GITHUB_TOKEN)
        st.text("GitHub数据管理器已初始化")
    except Exception as e:
        st.error(f"初始化GitHub管理器失败: {e}")
        github_manager = None

#页面显示
st.write('Loading Data...')
st.text('----Getting Fixture Data...')

# Getting Spot Fixture Data
#「兜底备份」函数：当 API 无法访问、网络故障、或者本地想快速调试时，不拉实时接口，直接读本地一份静态全历史文件 Baltic Exchange - Historic Data.csv，返回同样结构的 DataFrame，让后续代码无感知切换。
@st.cache_data()
def load_spot_data_backup():
    spot=pd.read_csv('Baltic Exchange - Historic Data.csv')
    spot.set_index('date',inplace=True)
    spot.index=pd.to_datetime(spot.index,dayfirst=True) #强制把索引转成时间索引；dayfirst=True 告诉解析器「日/月/年」格式（欧洲风格）。
    #spot=spot[spot.index>=pd.to_datetime(date(2015,1,1))]

    return spot

# ----------  通用引擎字符匹配函数 ----------
def enrich(df: pd.DataFrame, maps: dict) -> pd.DataFrame:
    """
    对 DataFrame 中指定列进行"空值补全"：
    1. 原列已有非空值 → 原样保留
    2. 原列为 NaN / 空字符串 / 仅空格 → 用正则从 fixtureString 提取并填充
    3. 若字典中的列名在表中不存在 → 先创建全 NaN 列，再按规则填充
    返回：填充后的新 DataFrame（不修改原表）
    """
    # 深拷贝，避免修改原表
    df = df.copy()

    # 统一把 fixtureString 转成字符串，防止 NaN 导致正则报错
    txt = df['fixtureString'].astype(str)

    # 遍历正则地图 {字段名: 编译好的正则}
    for col, pat in maps.items():
        # 如果该列在表中不存在（例如新增 Via/Redel/Hire），先创建全 NaN 列
        if col not in df.columns:
            df[col] = None

        # 构造掩码：True 表示需要补全（NaN 或空字符串或仅空格）
        mask = pd.isna(df[col]) | (df[col].astype(str).str.strip() == '')

        # 内部工具函数：对单行文本跑正则，命中返回捕获组1并去空格，否则返回 None
        def extract_text(x):
            if pd.isna(x):               # 本身是 NaN 直接返回 None
                return None
            m = pat.search(x)            # 跑正则
            return m.group(1).strip() if m else None  # 命中→去空格，未命中→None

        # 只对"空"行跑正则，结果写回同一列
        df.loc[mask, col] = txt[mask].apply(extract_text)

    # 返回填充/新增列后的新表
    return df

# ---------- 辅助函数：添加 VESSEL TYPE 列 ----------
def add_vessel_type(df):
    """根据 dwt 列添加 VESSEL TYPE 列"""
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # 确保 dwt 列存在
    if 'dwt' not in df.columns:
        df['dwt'] = None
    
    # 处理 dwt 列：转换为数值，去除逗号等
    def parse_dwt(x):
        if pd.isna(x):
            return None
        try:
            # 去除逗号和空格
            x_str = str(x).replace(',', '').strip()
            # 提取数字部分
            match = re.search(r'(\d+)', x_str)
            if match:
                return int(match.group(1))
            return None
        except:
            return None
    
    # 创建数值型的 dwt 列用于判断
    df['dwt_numeric'] = df['dwt'].apply(parse_dwt)
    
    # 根据 dwt_numeric 判断船舶类型
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
    
    # 添加 VESSEL TYPE 列
    df['VESSEL TYPE'] = df['dwt_numeric'].apply(determine_vessel_type)
    
    # 删除临时的 dwt_numeric 列
    if 'dwt_numeric' in df.columns:
        df = df.drop(columns=['dwt_numeric'])
    
    return df

# ==================== 批量请求API函数 ====================
@st.cache_data(ttl=3600)  # 缓存1小时，减少API调用
def fetch_all_fixtures_data(days_back: int = 1):
    """
    批量获取所有fixture类型的数据，减少API调用次数
    使用指数退避策略处理429错误
    """
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto = pd.to_datetime('today')- BDay(1)
    datefrom = dateto - BDay(days_back)
    params = {'from': datefrom, 'to': dateto}
    
    # API端点映射：类型名 -> (API URL, 使用的列, 正则映射)
    api_configs = {
        'timecharter': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXT3NN4TMQPQL3YB0HRAMQKPSI3CCLKO/data',
            'use_cols': [
                'date', 'fixtureType', 'shipName', 
                'buildYear', 'dwt', 'deliveryPort', 'freeText', 'loadArea', 
                'charterer', 'comment', 'tripDescriptionPeriodInfo', 'viaPortReletRateBallastBonus','fixtureString'
            ]
        },
        'periodcharter': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTTRVOV52RXY20H2JXIGEQ3JSK2LRDH/data',
            'use_cols': [
                'date', 'fixtureType', 'voyageType', 'shipName', 
                'buildYear', 'dwt', 'deliveryPort', 'freeText', 'loadArea', 
                'charterer', 'comment', 'tripDescriptionPeriodInfo', 'fixtureString'
            ]
        },
        'voyage_grain': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTK49ZE0UEYV553O9AMBJAC201AUIBG/data',
            'use_cols': [
                'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
                'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
                'charterer', 'comment','fixtureString'
            ]
        },
        'voyage_coal': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTUG0D1YCOCHBLVRKBQPXIXI6L2X5TA/data',
            'use_cols': [
                'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
                'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
                'charterer', 'comment','fixtureString'
            ]
        },
        'voyage_misc': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTLE3TOJ4YRBE3VAD4TWRY42LOJUKET/data',
            'use_cols': [
                'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
                'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
                'charterer', 'comment','fixtureString'
            ]
        },
        'voyage_ore': {
            'url': 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXT1RAFAFHAFWQM3SKLQ4SE9TQ4VTT2O/data',
            'use_cols': [
                'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
                'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
                'charterer', 'comment','fixtureString'
            ]
        }
    }
    
    results = {}
    session = requests.Session()  # 使用会话对象复用连接
    session.headers.update(headers)
    
    for name, config in api_configs.items():
        max_retries = 3  # 最大重试次数
        for attempt in range(max_retries):
            try:
                # 增加随机延迟，避免固定间隔被识别为爬虫
                if attempt > 0:  # 如果不是第一次尝试，使用指数退避
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    st.info(f"等待 {wait_time:.1f} 秒后重试 {name}...")
                    time.sleep(wait_time)
                elif name != list(api_configs.keys())[0]:  # 第一个请求后添加基础延迟
                    time.sleep(2 + random.uniform(0, 1))  # 2-3秒随机延迟
                
                response = session.get(config['url'], params=params, timeout=15)
                
                if response.status_code == 429:  # Too Many Requests
                    st.warning(f"{name} API 请求过于频繁，尝试 {attempt+1}/{max_retries}")
                    if attempt == max_retries - 1:  # 最后一次尝试也失败
                        st.error(f"{name} API 请求失败，使用本地缓存数据")
                        results[name] = {'fixtures': []}
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                # 检查返回数据是否有效
                if 'fixtures' not in data:
                    st.warning(f"{name} API 返回数据格式异常")
                    results[name] = {'fixtures': []}
                else:
                    results[name] = data
                    st.text(f"成功获取 {name} 数据: {len(data.get('fixtures', []))} 条记录")
                break  # 成功获取数据，跳出重试循环
                
            except requests.exceptions.RequestException as e:
                st.error(f"获取 {name} 数据出错: {e}")
                if attempt == max_retries - 1:  # 最后一次尝试也失败
                    results[name] = {'fixtures': []}  # 返回空数据
    
    return results, api_configs

# ==================== TC类型正则补全使用 ====================
TC_RE_MAPS = {
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #但因中船名后面的四位数字抓出来
    'dwt': re.compile(r"(\d+)\s+dwt", re.I), #dwt前一串数字抓出来，即dwt的部分
    'deliveryPort': re.compile(r"dely\s+(.*?)(?=\s+(?:\d+(?:/\d+)?\s+\w+|prompt)\s+trip\b)", re.I),#从 dely 后面开始，任意字符（非贪婪）一直往前扫，直到第一次出现'数字+任意单词+trip' 或 'prompt+trip' 就停，把中间那段任意字符作为交船港口名返回。
    'freeText': re.compile(r'dely[\s\S]*?\b(\d+(?:/\d+)?\s+[A-Za-z]+|prompt)(?=\s+trip\b)', re.I),#抓del+字符后面的 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'via': re.compile(r'\bvia\s+(.*?)(?=\s+redel\b)', re.I),#via和redl之间的字符
    'redel': re.compile(r'\bredel\s+(.*?)(?=\s*\$)', re.I),#redel和$之间的内容
    'hire': re.compile(r'(\$.*?)(?:\s*-|$)', re.I),#从第一个美元符号开始，一直吞到第一个 - 或行尾之前结束，内容不限
}

@st.cache_data()
def process_tc_data(all_data, api_configs, days_back: int = 1):
    """
    处理TIMECHARTER数据
    """
    data = all_data.get('timecharter')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('timecharter.csv'):
        try:
            spot_old = github_manager.load_fixture_data('timecharter.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载TIMECHARTER数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载TIMECHARTER数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到TIMECHARTER API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in TIMECHARTER response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['timecharter']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['timecharter']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"TIMECHARTER 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_tcfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=TC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_tcfix.set_index('date', inplace=True)

        # 添加 VESSEL TYPE 列
        spot_tcfix = add_vessel_type(spot_tcfix)
        
        # 检查新数据是否为空
        if spot_tcfix.empty:
            st.warning("TIMECHARTER: 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'TIMECHARTER GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_tcfix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_tcfix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'timecharter.csv', 'TIMECHARTER')
                if not success:
                    st.error("TIMECHARTER数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_tcfix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的TIMECHARTER数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'timecharter.csv', 'TIMECHARTER')
                if not success:
                    st.error("TIMECHARTER数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理TIMECHARTER数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

# ==================== PERIOD类型正则补全使用 ====================
PERIOD_RE_MAPS={
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #船名后面的四位数字抓出来
    'dwt': re.compile(r"(\d+)\s+dwt", re.I), #dwt前一串数字抓出来，即dwt的部分
    'deliveryPort': re.compile(r"dely\s+(.*?)(?=\s+(?:\d+(?:/\d+)?\s+\w+|prompt)\s+)", re.I),#从 dely 后面开始，任意字符（非贪婪）一直往前扫，直到第一次出现'数字+任意单词 或 'prompt' 就停，把中间那段任意字符作为交船港口名返回。
    'freeText': re.compile(r'dely[\s\S]*?\b(\d+(?:/\d+)?\s+[A-Za-z]+|prompt)(?=\s+redel\b)', re.I),#抓 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'redel': re.compile(r'\bredel\s+(.*?)(?=\s*\$)', re.I),#redel和$之间的内容
    'hire': re.compile(r'(\$.*?)(?:\s*-|$)', re.I),#从第一个美元符号开始，一直吞到第一个 - 或行尾之前结束，内容不限
}

@st.cache_data()
def process_period_data(all_data, api_configs, days_back: int = 1):
    """
    处理PERIOD数据
    """
    data = all_data.get('periodcharter')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('periodcharter.csv'):
        try:
            spot_old = github_manager.load_fixture_data('periodcharter.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载PERIOD数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载PERIOD数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到PERIOD API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in PERIOD response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['periodcharter']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['periodcharter']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"PERIOD 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_periodfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=PERIOD_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_periodfix.set_index('date', inplace=True)
        
        # 添加 VESSEL TYPE 列
        spot_periodfix = add_vessel_type(spot_periodfix)
        
        # 检查新数据是否为空
        if spot_periodfix.empty:
            st.warning("PERIOD: 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'PERIOD GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_periodfix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_periodfix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'periodcharter.csv', 'PERIOD')
                if not success:
                    st.error("PERIOD数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_periodfix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的PERIOD数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'periodcharter.csv', 'PERIOD')
                if not success:
                    st.error("PERIOD数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理PERIOD数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

# ==================== VOYAGE类型正则补全使用 ====================
VC_RE_MAPS={
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #船名后面的四位数字抓出来
    'cargoSize': re.compile(r"(\d+/\d+)", re.I), #把70000/5这样的抓出来
    'freeText': re.compile(r"\b(\d+(?:/\d+)?\s+[A-Za-z]+)\b", re.I),#抓 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'freight': re.compile(r'(\$[^\s]*(?:\s[^\s]*)?)', re.I),#第一个美元符号开始、直到遇到第二个空格前"的运费金额
}

@st.cache_data()
def process_voyage_grain_data(all_data, api_configs, days_back: int = 1):
    """
    处理VOYAGE(GRAIN)数据
    """
    data = all_data.get('voyage_grain')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('voyage_grain.csv'):
        try:
            spot_old = github_manager.load_fixture_data('voyage_grain.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载VOYAGE(GRAIN)数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载VOYAGE(GRAIN)数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到VOYAGE(GRAIN) API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in VOYAGE(GRAIN) response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['voyage_grain']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['voyage_grain']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"VOYAGE(GRAIN) 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_vcgrfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcgrfix.set_index('date', inplace=True)
        
        # 添加 VESSEL TYPE 列
        spot_vcgrfix = add_vessel_type(spot_vcgrfix)
        
        # 检查新数据是否为空
        if spot_vcgrfix.empty:
            st.warning("VOYAGE(GRAIN): 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'VOYAGE(GRAIN) GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_vcgrfix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_vcgrfix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_grain.csv', 'VOYAGE(GRAIN)')
                if not success:
                    st.error("VOYAGE(GRAIN)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_vcgrfix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的VOYAGE(GRAIN)数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_grain.csv', 'VOYAGE(GRAIN)')
                if not success:
                    st.error("VOYAGE(GRAIN)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理VOYAGE(GRAIN)数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

@st.cache_data()
def process_voyage_coal_data(all_data, api_configs, days_back: int = 1):
    """
    处理VOYAGE(COAL)数据
    """
    data = all_data.get('voyage_coal')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('voyage_coal.csv'):
        try:
            spot_old = github_manager.load_fixture_data('voyage_coal.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载VOYAGE(COAL)数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载VOYAGE(COAL)数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到VOYAGE(COAL) API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in VOYAGE(COAL) response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['voyage_coal']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['voyage_coal']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"VOYAGE(COAL) 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_vccofix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vccofix.set_index('date', inplace=True)
        
        # 添加 VESSEL TYPE 列
        spot_vccofix = add_vessel_type(spot_vccofix)
        
        # 检查新数据是否为空
        if spot_vccofix.empty:
            st.warning("VOYAGE(COAL): 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'VOYAGE(COAL) GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_vccofix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_vccofix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_coal.csv', 'VOYAGE(COAL)')
                if not success:
                    st.error("VOYAGE(COAL)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_vccofix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的VOYAGE(COAL)数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_coal.csv', 'VOYAGE(COAL)')
                if not success:
                    st.error("VOYAGE(COAL)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理VOYAGE(COAL)数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

@st.cache_data()
def process_voyage_misc_data(all_data, api_configs, days_back: int = 1):
    """
    处理VOYAGE(MISC)数据
    """
    data = all_data.get('voyage_misc')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('voyage_misc.csv'):
        try:
            spot_old = github_manager.load_fixture_data('voyage_misc.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载VOYAGE(MISC)数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载VOYAGE(MISC)数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到VOYAGE(MISC) API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in VOYAGE(MISC) response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['voyage_misc']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['voyage_misc']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"VOYAGE(MISC) 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_vcmifix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcmifix.set_index('date', inplace=True)
        
        # 添加 VESSEL TYPE 列
        spot_vcmifix = add_vessel_type(spot_vcmifix)
        
        # 检查新数据是否为空
        if spot_vcmifix.empty:
            st.warning("VOYAGE(MISC): 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'VOYAGE(MISC) GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_vcmifix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_vcmifix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_misc.csv', 'VOYAGE(MISC)')
                if not success:
                    st.error("VOYAGE(MISC)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_vcmifix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的VOYAGE(MISC)数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_misc.csv', 'VOYAGE(MISC)')
                if not success:
                    st.error("VOYAGE(MISC)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理VOYAGE(MISC)数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

@st.cache_data()
def process_voyage_ore_data(all_data, api_configs, days_back: int = 1):
    """
    处理VOYAGE(ORE)数据
    """
    data = all_data.get('voyage_ore')
    
    # 尝试从GitHub加载现有数据
    spot_old = None
    if github_manager and github_manager.file_exists('voyage_ore.csv'):
        try:
            spot_old = github_manager.load_fixture_data('voyage_ore.csv')
            if spot_old is not None and not spot_old.empty:
                spot_old.set_index('date', inplace=True)
                st.text(f'从GitHub加载VOYAGE(ORE)数据: {len(spot_old)} 条记录，最新日期: {spot_old.index[-1].date()}')
        except Exception as e:
            st.warning(f"从GitHub加载VOYAGE(ORE)数据失败: {e}")
    
    if not data or 'fixtures' not in data or not data['fixtures']:
        st.warning("未获取到VOYAGE(ORE) API数据")
        # 如果API没有数据，返回现有数据（不更新GitHub）
        return spot_old if spot_old is not None and not spot_old.empty else None
    
    try:
        # 处理fixtures数据
        fixtures = data['fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回现有数据
        if not fixtures:
            st.warning("No fixtures data available in VOYAGE(ORE) response")
            return spot_old if spot_old is not None and not spot_old.empty else None
            
        fixtures_df = pd.DataFrame(fixtures)
        
        # 如果fixtures_df为空，直接返回现有数据
        if fixtures_df.empty:
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 使用配置中的列
        use_cols = [col for col in api_configs['voyage_ore']['use_cols'] if col in fixtures_df.columns]
        missing_cols = set(api_configs['voyage_ore']['use_cols']) - set(use_cols)
        if missing_cols:
            st.text(f"VOYAGE(ORE) 数据缺少列: {missing_cols}")
        
        # 处理新数据
        spot_vcorfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcorfix.set_index('date', inplace=True)
        
        # 添加 VESSEL TYPE 列
        spot_vcorfix = add_vessel_type(spot_vcorfix)
        
        # 检查新数据是否为空
        if spot_vcorfix.empty:
            st.warning("VOYAGE(ORE): 新获取的数据为空")
            return spot_old if spot_old is not None and not spot_old.empty else None
        
        # 合并数据
        if spot_old is not None and not spot_old.empty:
            st.text(f'VOYAGE(ORE) GitHub数据更新前: {spot_old.index[-1].date()}')
            
            # 合并所有数据（包括旧数据和新数据）
            spot_combined = pd.concat([spot_old, spot_vcorfix])
            
            # 重置索引以便去重
            spot_combined = spot_combined.reset_index()
            
            # 基于date和shipName去重，保留最新的（最后出现的）
            spot_combined = spot_combined.drop_duplicates(keep='last')
            
            # 重新设置索引
            spot_combined.set_index('date', inplace=True)
            spot_combined.sort_index(inplace=True)
            
            st.text(f'合并后数据条数: {len(spot_combined)}，新数据条数: {len(spot_vcorfix)}')
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_ore.csv', 'VOYAGE(ORE)')
                if not success:
                    st.error("VOYAGE(ORE)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
        else:
            # 没有旧数据，直接使用新数据
            spot_combined = spot_vcorfix
            spot_combined.sort_index(inplace=True)
            st.text("创建新的VOYAGE(ORE)数据集")
            
            # 保存到GitHub（自动保存，不需要按钮）
            if github_manager:
                success = github_manager.save_fixture_data(spot_combined.reset_index(), 'voyage_ore.csv', 'VOYAGE(ORE)')
                if not success:
                    st.error("VOYAGE(ORE)数据保存到GitHub失败")
            else:
                st.warning("GitHub管理器未初始化，数据未保存")
            
            return spot_combined
    
    except Exception as e:
        st.error(f"处理VOYAGE(ORE)数据时出错: {e}")
        import traceback
        st.error(traceback.format_exc())
        return spot_old if spot_old is not None and not spot_old.empty else None

# ==================== 数据加载主函数 ====================

#手动拉取前15天的数据，避免断更产生的影响
def update_data():
    # 1) 清掉所有旧缓存
    st.cache_data.clear()
    # 2) 告诉 loader 这次要抓 15 天
    st.session_state['force_15_days'] = True #如果用户点过更新函数，那么session里会存在force_15_days的key
    # 得到true之后需要重新运行脚本，才能使用
    st.rerun() #拿到true之后立即重新运行脚本

#如果session里会存在force_15_days的key，那么days_back就设置为15，用pop是用一次之后就删掉
days_back = 15 if st.session_state.pop('force_15_days', None) else 1 

"""
pop(key, None) 会把 key 对应的值取出来同时删掉；如果 key 不存在就返回 None。
因此：
– 用户没点按钮 → 没有 'force_15_days' → pop 返回 None → days_back = 1（日常增量）。
– 用户点了按钮 → 回调里把 'force_15_days' 设成 True → 脚本立即 st.rerun() → 第二次跑到这里时 pop 取出 True 并删掉 → days_back = 15（补 15 天）。
– 再下一次刷新页面 → 标记已被删 → 又回到 1。

"""

# 批量获取所有数据
st.text("批量获取所有fixture数据...")
all_data, api_configs = fetch_all_fixtures_data(days_back)

# 处理TIMECHARTER数据
st.text("处理TIMECHARTER数据...")
tc_spot = process_tc_data(all_data, api_configs, days_back)
if tc_spot is not None:
    st.session_state['tc_spot'] = tc_spot
    st.text(f'TIMECHARTER数据: {len(tc_spot)} 条记录')
else:
    st.warning("TIMECHARTER数据为空")

# 处理PERIOD数据
st.text("处理PERIOD数据...")
period_spot = process_period_data(all_data, api_configs, days_back)
if period_spot is not None:
    st.session_state['period_spot'] = period_spot
    st.text(f'PERIOD数据: {len(period_spot)} 条记录')
else:
    st.warning("PERIOD数据为空")

# 处理VOYAGE(GRAIN)数据
st.text("处理VOYAGE(GRAIN)数据...")
vcgr_spot = process_voyage_grain_data(all_data, api_configs, days_back)
if vcgr_spot is not None:
    st.session_state['vcgr_spot'] = vcgr_spot
    st.text(f'VOYAGE(GRAIN)数据: {len(vcgr_spot)} 条记录')
else:
    st.warning("VOYAGE(GRAIN)数据为空")

# 处理VOYAGE(COAL)数据
st.text("处理VOYAGE(COAL)数据...")
vcco_spot = process_voyage_coal_data(all_data, api_configs, days_back)
if vcco_spot is not None:
    st.session_state['vcco_spot'] = vcco_spot
    st.text(f'VOYAGE(COAL)数据: {len(vcco_spot)} 条记录')
else:
    st.warning("VOYAGE(COAL)数据为空")

# 处理VOYAGE(MISC)数据
st.text("处理VOYAGE(MISC)数据...")
vcmi_spot = process_voyage_misc_data(all_data, api_configs, days_back)
if vcmi_spot is not None:
    st.session_state['vcmi_spot'] = vcmi_spot
    st.text(f'VOYAGE(MISC)数据: {len(vcmi_spot)} 条记录')
else:
    st.warning("VOYAGE(MISC)数据为空")

# 处理VOYAGE(ORE)数据
st.text("处理VOYAGE(ORE)数据...")
vcor_spot = process_voyage_ore_data(all_data, api_configs, days_back)
if vcor_spot is not None:
    st.session_state['vcor_spot'] = vcor_spot
    st.text(f'VOYAGE(ORE)数据: {len(vcor_spot)} 条记录')
else:
    st.warning("VOYAGE(ORE)数据为空")

st.text('Fixture Data Done')
st.write('All Data Loaded!!')

# 只保留Update Data按钮，移除Sync All to GitHub按钮
st.button('Update Data', on_click=update_data)

st.text('Data will be updated when streamlit is opened')
st.text('If you would like to trigger the reload right now, please click on the above "Update Data" button.')
