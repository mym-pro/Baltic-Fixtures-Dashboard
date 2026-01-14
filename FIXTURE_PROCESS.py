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

# 添加配置管理模块
try:
    from config_manager import ConfigManager, init_session_config
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    st.warning("配置管理模块未找到，将创建默认配置管理器")

pd.set_option('display.max_rows',None)
pd.set_option('display.max_columns',None)
#让 DataFrame 不管多少行都 全部打印出来，不再出现中间省略号，这两行只是方便 开发调试阶段 在控制台里一眼看全表；上线后可以保留，也可以删掉，对最终用户界面没有任何影响。

# ==================== 初始化配置 ====================
def initialize_config():
    """初始化配置管理系统"""
    if CONFIG_MANAGER_AVAILABLE:
        try:
            init_session_config()
            st.success("✅ 配置系统已初始化")
            
            # 显示配置状态
            if 'app_config' in st.session_state:
                config = st.session_state.app_config
                if 'custom_sets' in config:
                    set_count = len(config['custom_sets'])
                    st.info(f"📚 加载了 {set_count} 个自定义筛选集合")
                else:
                    st.info("📚 无自定义筛选集合，请在数据管理页面创建")
        except Exception as e:
            st.warning(f"配置初始化失败: {e}")
            # 创建基本的配置管理器
            create_fallback_config()
    else:
        # 创建基本的配置管理器
        create_fallback_config()

def create_fallback_config():
    """创建回退配置"""
    default_config = {
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
                "created_at": date.today().isoformat(),
                "is_template": True
            },
            "ECSA": {
                "keywords": ["ECSA", "EAST COAST SOUTH AMERICA", "BRAZIL", "ARGENTINA", "URUGUAY"],
                "description": "东海岸南美洲港口",
                "created_at": date.today().isoformat(),
                "is_template": True
            },
            "USG": {
                "keywords": ["US GULF", "USGC", "GULF COAST", "HOUSTON", "NEW ORLEANS"],
                "description": "美国墨西哥湾港口",
                "created_at": date.today().isoformat(),
                "is_template": True
            }
        },
        "version": "2.0",
        "last_modified": date.today().isoformat()
    }
    
    # 保存到 session state
    st.session_state.app_config = default_config
    st.info("📚 使用默认配置，包含 3 个预定义筛选集合")

# 初始化配置
initialize_config()

#页面显示
st.write('Loading Data...')
st.text('----Getting Fixture Data...')

#Getting Spot Fixture Data
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

#TC类型正则补全使用
TC_RE_MAPS = {
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #但因中船名后面的四位数字抓出来
    'dwt': re.compile(r"(\d+)\s+dwt", re.I), #dwt前一串数字抓出来，即dwt的部分
    'deliveryPort': re.compile(r"dely\s+(.*?)(?=\s+(?:\d+(?:/\d+)?\s+\w+|prompt)\s+trip\b)", re.I),#从 dely 后面开始，任意字符（非贪婪）一直往前扫，直到第一次出现"数字+任意单词+trip" 或 "prompt+trip" 就停，把中间那段任意字符作为交船港口名返回。
    'freeText': re.compile(r'dely[\s\S]*?\b(\d+(?:/\d+)?\s+[A-Za-z]+|prompt)(?=\s+trip\b)', re.I),#抓del+字符后面的 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'via': re.compile(r'\bvia\s+(.*?)(?=\s+redel\b)', re.I),#via和redl之间的字符
    'redel': re.compile(r'\bredel\s+(.*?)(?=\s*\$)', re.I),#redel和$之间的内容
    'hire': re.compile(r'(\$.*?)(?:\s*-|$)', re.I),#从第一个美元符号开始，一直吞到第一个 - 或行尾之前结束，内容不限
}
@st.cache_data()
def load_tc_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_tc='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXT3NN4TMQPQL3YB0HRAMQKPSI3CCLKO/data'
   # 通过接口获取TC-FIXTURES数据
    """
    "name": "TIMECHARTER",
     "apiIdentifier": "FXT3NN4TMQPQL3YB0HRAMQKPSI3CCLKO",
     "fixturesFrom": "2026-01-08",
     "fixturesTo": "2026-01-08",
     "fixtures": [
    {
      "date": "2026-01-08",
      "fixtureType": "TIMECHARTER",

    
    """
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_tc, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from TIMECHARTER API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'shipName', 
    'buildYear', 'dwt', 'deliveryPort', 'freeText', 'loadArea', 
    'charterer', 'comment', 'tripDescriptionPeriodInfo', 'viaPortReletRateBallastBonus','fixtureString']
       # 确保所有需要的列都存在
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_tcfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=TC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_tcfix.set_index('date', inplace=True)

        # 添加 VESSEL TYPE 列
        spot_tcfix = add_vessel_type(spot_tcfix)
        
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'timecharter.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)

            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)

            st.text(f'TIMECHARTER Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_tcfix[spot_tcfix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_tcfix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'TIMECHARTER Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No tc fixtures data available.")
        return None

PERIOD_RE_MAPS={
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #船名后面的四位数字抓出来
    'dwt': re.compile(r"(\d+)\s+dwt", re.I), #dwt前一串数字抓出来，即dwt的部分
    'deliveryPort': re.compile(r"dely\s+(.*?)(?=\s+(?:\d+(?:/\d+)?\s+\w+|prompt)\s+)", re.I),#从 dely 后面开始，任意字符（非贪婪）一直往前扫，直到第一次出现"数字+任意单词 或 "prompt" 就停，把中间那段任意字符作为交船港口名返回。
    'freeText': re.compile(r'dely[\s\S]*?\b(\d+(?:/\d+)?\s+[A-Za-z]+|prompt)(?=\s+redel\b)', re.I),#抓 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'redel': re.compile(r'\bredel\s+(.*?)(?=\s*\$)', re.I),#redel和$之间的内容
    'hire': re.compile(r'(\$.*?)(?:\s*-|$)', re.I),#从第一个美元符号开始，一直吞到第一个 - 或行尾之前结束，内容不限
}
@st.cache_data()
def load_period_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_period='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTTRVOV52RXY20H2JXIGEQ3JSK2LRDH/data'
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_period, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from Period API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'voyageType', 'shipName', 
    'buildYear', 'dwt', 'deliveryPort', 'freeText', 'loadArea', 
    'charterer', 'comment', 'tripDescriptionPeriodInfo', 'fixtureString']
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_periodfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=PERIOD_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_periodfix.set_index('date', inplace=True)
        # 添加 VESSEL TYPE 列
        spot_periodfix = add_vessel_type(spot_periodfix)
        
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'periodcharter.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)
            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)
            st.text(f'PERIOD Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_periodfix[spot_periodfix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_periodfix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'PERIOD Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No period fixtures data available.")
        return None

VC_RE_MAPS={
    # chrtr不匹配了，因为好像都写了，而且比较难匹配，因为不好定位--
    'shipName': re.compile(r"'([^']+)'", re.I), #找到第一对单引号，把中间不是单引号的那串字符抓出来，就是船名。re.I忽略大小写
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I), #船名后面的四位数字抓出来
    'cargoSize': re.compile(r"(\d+/\d+)", re.I), #把70000/5这样的抓出来
    'freeText': re.compile(r"\b(\d+(?:/\d+)?\s+[A-Za-z]+)\b", re.I),#抓 数字+任意长度月份单词 或 prompt
    'comment': re.compile(r"<([^>]+)>", re.I),#取第一对尖括号 <...> 之间的任意字符
    'freight': re.compile(r'(\$.*?)(?:\s*)', re.I),#第一个美元符号开始、直到遇到空格前"的运费金额
}
@st.cache_data()
def load_voyage_grain_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_voyage_grain='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTK49ZE0UEYV553O9AMBJAC201AUIBG/data'
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_voyage_grain, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from voyage grain API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
    'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
    'charterer', 'comment','fixtureString']
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_vcgrfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcgrfix.set_index('date', inplace=True)
        # 添加 VESSEL TYPE 列
        spot_vcgrfix = add_vessel_type(spot_vcgrfix)
        
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'vcgrain.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)
            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)
            st.text(f'VOYAGE(GRAIN) Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_vcgrfix[spot_vcgrfix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_vcgrfix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'VOYAGE(GRAIN) Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No voyage grain fixtures data available.")
        return None


@st.cache_data()
def load_voyage_coal_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_voyage_coal='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTUG0D1YCOCHBLVRKBQPXIXI6L2X5TA/data'
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_voyage_coal, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from voyage coal API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
    'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
    'charterer', 'comment','fixtureString']
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_vccofix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vccofix.set_index('date', inplace=True)
        # 添加 VESSEL TYPE 列
        spot_vccofix = add_vessel_type(spot_vccofix)
        
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'vccoal.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)
            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)
            st.text(f'VOYAGE(COAL) Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_vccofix[spot_vccofix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_vccofix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'VOYAGE(COAL) Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No voyage coal fixtures data available.")
        return None


@st.cache_data()
def load_voyage_misc_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_voyage_misc='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXTLE3TOJ4YRBE3VAD4TWRY42LOJUKET/data'
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_voyage_misc, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from voyage misc API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
    'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
    'charterer', 'comment','fixtureString']
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_vcmifix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcmifix.set_index('date', inplace=True)
         # 添加 VESSEL TYPE 列
        spot_vcmifix = add_vessel_type(spot_vcmifix)       
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'vcmisc.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)
            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)
            st.text(f'VOYAGE(MISC) Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_vcmifix[spot_vcmifix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_vcmifix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'VOYAGE(MISC) Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No voyage misc fixtures data available.")
        return None
    

@st.cache_data()
def load_voyage_ore_data(days_back: int = 1):
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto=pd.to_datetime('today')-BDay(1) #获取代码运行当日日期
    datefrom=dateto-BDay(days_back) #向前推15个工作日，不考虑节假日，得到15日的数据。意思是允许断更15天。因为可能有15天不打开链接，那么他就没法更新，如果比如说一个月没打开，那么就需要改成31。但是fixture的数据不需要每天连续更新，所以往前推两天就够了
    params={'from':datefrom,'to':dateto}
    url_voyage_ore='https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXT1RAFAFHAFWQM3SKLQ4SE9TQ4VTT2O/data'
   # 通过接口获取TC-FIXTURES数据
    #检查一下获取到的数据是否有效
    try:
        response = requests.get(url_voyage_ore, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 检查返回数据是否有效
        if 'fixtures' not in data or not data['fixtures']:
            st.warning(f"No fixtures data returned for the period {datefrom.date()} to {dateto.date()}")
            return None
            
        df = pd.DataFrame(data)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from voyage ore API: {e}")
        return None
    use_cols = [
    'date', 'fixtureType', 'cargoSize','voyageType', 'shipName', 
    'buildYear', 'dwt',  'freeText', 'loadPort', 'dischargePort','rateAndTerms',
    'charterer', 'comment','fixtureString']
    # 确保所有需要的列都存在
    if 'fixtures' in df.columns and len(df) > 0:
        # 修复：处理fixtures可能为单个字典的情况
        fixtures = df.loc[0, 'fixtures']
        
        # 如果fixtures是字典（单个数据点），转换为列表
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        # 如果fixtures是空列表，直接返回None
        if not fixtures:
            st.warning("No fixtures data available in the response")
            return None
            
        fixtures_df = pd.DataFrame(fixtures)  # 现在这里应该是安全的
        
        # 如果fixtures_df为空，直接返回None
        if fixtures_df.empty:
            return None
        
        spot_vcorfix = (fixtures_df[use_cols]
                      .pipe(enrich, maps=VC_RE_MAPS)
                      .assign(date=lambda x: pd.to_datetime(x['date'])))
        spot_vcorfix.set_index('date', inplace=True)
         # 添加 VESSEL TYPE 列
        spot_vcorfix = add_vessel_type(spot_vcorfix)       
        # 读取或创建旧数据文件，如果没有旧数据文件则创建
        file_path = 'vcore.csv'
        if os.path.exists(file_path):
            spot_old = pd.read_csv(file_path, parse_dates=['date'])
            spot_old.set_index('date', inplace=True)
            # 确保旧数据也有 VESSEL TYPE 列（如果是从旧版本升级）
            if 'VESSEL TYPE' not in spot_old.columns:
                spot_old = add_vessel_type(spot_old)
            st.text(f'VOYAGE(ORE) Fixtures Data Before Update: {spot_old.index[-1].date()}')
            
            # 合并数据 - 只保留不在旧数据中的新数据
            # 假设新数据的日期都在旧数据最新日期之后
            last_date = spot_old.index.max()
            new_data = spot_vcorfix[spot_vcorfix.index > last_date]
            
            if not new_data.empty:
                spot = pd.concat([spot_old, new_data])
            else:
                spot = spot_old
                st.info("No new data to add.")
        else:
            spot = spot_vcorfix
            st.text("Creating new data file.")
        
        # 去重
        spot = spot.reset_index()
        spot = spot.drop_duplicates(subset=['date', 'shipName'], keep='last')
        spot.set_index('date', inplace=True)
        spot.sort_index(inplace=True)
        
        st.text(f'VOYAGE(ORE) Fixtures Data After Update: {spot.index[-1].date()}')
        st.text(f'Total records: {len(spot)}')
        
        # 保存
        spot.to_csv(file_path, index_label='date')
        
        return spot
    
    else:
        st.warning("No voyage misc fixtures data available.")
        return None




#手动拉取前15天的数据，避免断更产生的影响
def update_data():
    # 1) 清掉所有旧缓存
    st.cache_data.clear()
    # 2) 告诉 loader 这次要抓 15 天
    st.session_state['force_15_days'] = True #如果用户点过更新函数，那么session里会存在force_15_days的key
    # 得到true之后需要重新运行脚本，才能使用
    st.rerun() #拿到true之后立即重新运行脚本

#如果session里会存在force_15_days的key，那么days_back就设置为15，用pop是用一次之后就删掉
days_back = 3 if st.session_state.pop('force_15_days', None) else 1 

"""
pop(key, None) 会把 key 对应的值取出来同时删掉；如果 key 不存在就返回 None。
因此：
– 用户没点按钮 → 没有 'force_15_days' → pop 返回 None → days_back = 2（日常增量）。
– 用户点了按钮 → 回调里把 'force_15_days' 设成 True → 脚本立即 st.rerun() → 第二次跑到这里时 pop 取出 True 并删掉 → days_back = 15（补 15 天）。
– 再下一次刷新页面 → 标记已被删 → 又回到 2。

"""
 
time.sleep(1)  # 初始延迟
tc_spot = load_tc_data(days_back)
if 'tc_spot' not in st.session_state:
    st.session_state['tc_spot'] = tc_spot

time.sleep(1)  # 请求之间添加延迟
period_spot = load_period_data(days_back)
if 'period_spot' not in st.session_state:
    st.session_state['period_spot'] = period_spot

time.sleep(1)
vcgr_spot = load_voyage_grain_data(days_back)
if 'vcgr_spot' not in st.session_state:
    st.session_state['vcgr_spot'] = vcgr_spot

time.sleep(1)
vcco_spot = load_voyage_coal_data(days_back)
if 'vcco_spot' not in st.session_state:
    st.session_state['vcco_spot'] = vcco_spot

time.sleep(1)
vcmi_spot = load_voyage_misc_data(days_back)
if 'vcmi_spot' not in st.session_state:
    st.session_state['vcmi_spot'] = vcmi_spot

time.sleep(1)
vcor_spot = load_voyage_ore_data(days_back)
if 'vcor_spot' not in st.session_state:
    st.session_state['vcor_spot'] = vcor_spot

st.text('Fixture Data Done')
st.write('All Data Loaded!!')

st.button('Update Data',on_click=update_data) #按钮链接更新函数
st.text('Data will be updated when streamlit is opened')
st.text('If you would like to trigger the reload right now, please click on the above "Update Data" button.') 
