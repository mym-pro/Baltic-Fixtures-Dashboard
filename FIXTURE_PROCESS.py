# FIXTURE_PROCESS.py
# ----------------------------  0. 调试开关  ----------------------------
DEBUG = True  # 部署前改为 False

# ----------------------------  1. 环境初始化  ----------------------------
import streamlit as st
st.set_page_config(layout="wide")
st.title('Baltic Fixture Dashboard')

import warnings, requests, os, time, random, pandas as pd, re, numpy as np
from datetime import date
from pandas.tseries.offsets import BDay
warnings.simplefilter('ignore')

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

st.write('Loading Data...')
st.text('----Getting Fixture Data...')

# ----------------------------  2. 工具函数  ----------------------------
def enrich(df, maps):
    df = df.copy()
    txt = df['fixtureString'].astype(str)
    for col, pat in maps.items():
        if col not in df.columns:
            df[col] = None
        mask = pd.isna(df[col]) | (df[col].astype(str).str.strip() == '')
        df.loc[mask, col] = txt[mask].apply(lambda x: (pat.search(x).group(1).strip() if pat.search(x) else None))
    return df

def add_vessel_type(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    if 'dwt' not in df.columns:
        df['dwt'] = None
    def parse_dwt(x):
        if pd.isna(x):
            return None
        try:
            return int(re.search(r'(\d+)', str(x).replace(',', '')).group(1))
        except:
            return None
    df['dwt_numeric'] = df['dwt'].apply(parse_dwt)
    def dtype(d):
        if pd.isna(d):
            return None
        d = float(d)
        if d > 100_000:
            return 'CAPE/VLOC'
        elif d > 80_000:
            return 'KMX'
        elif d >= 65_000:
            return 'PMX'
        else:
            return 'SMX/UMX/HANDY'
    df['VESSEL TYPE'] = df['dwt_numeric'].apply(dtype)
    return df.drop(columns=['dwt_numeric'])

# ----------------------------  3. 正则地图  ----------------------------
TC_RE_MAPS = {
    'shipName': re.compile(r"'([^']+)'", re.I),
    'buildYear': re.compile(r"'[^']+'\s+(\d{4})", re.I),
    'dwt': re.compile(r"(\d+)\s+dwt", re.I),
    'deliveryPort': re.compile(r"dely\s+(.*?)(?=\s+(?:\d+(?:/\d+)?\s+\w+|prompt)\s+trip\b)", re.I),
    'freeText': re.compile(r'dely[\s\S]*?\b(\d+(?:/\d+)?\s+[A-Za-z]+|prompt)(?=\s+trip\b)', re.I),
    'comment': re.compile(r"<([^>]+)>", re.I),
    'via': re.compile(r'\bvia\s+(.*?)(?=\s+redel\b)', re.I),
    'redel': re.compile(r'\bredel\s+(.*?)(?=\s*\$)', re.I),
    'hire': re.compile(r'(\$.*?)(?:\s*-|$)', re.I),
}

# ----------------------------  4. TC 数据加载  ----------------------------
@st.cache_data(ttl=600)  # 10 分钟缓存，减少并发
def load_tc_data(days_back: int = 2):
    url = 'https://api.balticexchange.com/api/v1.3/feed/FDS08EK9KYT1G4A5POP8AX5PHUZWZYPZ/fixtureType/FXT3NN4TMQPQL3YB0HRAMQKPSI3CCLKO/data'
    headers = {'x-apikey': 'FMNNXJKJMSV6PE4YA36EOAAJXX1WAH84KSWNU8PEUFGRHUPJZA3QTG1FLE09SXJF'}
    dateto = pd.to_datetime('today')
    datefrom = dateto - BDay(days_back)
    params = {'from': datefrom.date(), 'to': dateto.date()}

    if DEBUG:
        print(f'[DEBUG] load_tc_data 开始 | days_back={days_back} | {datefrom.date()} ~ {dateto.date()}')

    # 429 退避重试
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 429:
                wait = random.uniform(1, 3) * attempt
                print(f'[DEBUG] 429 -> 等待 {wait:.1f}s 后重试（{attempt}/3）')
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 3:
                st.error(f'TC API 三次重试后仍失败：{e}')
                if DEBUG:
                    st.exception(e)
                return None
            time.sleep(1)
    else:
        return None

    data = resp.json()
    if 'fixtures' not in data or not data['fixtures']:
        st.warning('TC 无 fixtures 返回')
        return None

    df = pd.DataFrame(data)
    fixtures = df.loc[0, 'fixtures']
    if isinstance(fixtures, dict):
        fixtures = [fixtures]
    if not fixtures:
        st.warning('TC fixtures 为空列表')
        return None

    fixtures_df = pd.DataFrame(fixtures)
    use_cols = ['date', 'fixtureType', 'shipName', 'buildYear', 'dwt',
                'deliveryPort', 'freeText', 'loadArea', 'charterer',
                'comment', 'tripDescriptionPeriodInfo', 'viaPortReletRateBallastBonus', 'fixtureString']
    spot_tcfix = (fixtures_df[use_cols]
                  .pipe(enrich, maps=TC_RE_MAPS)
                  .assign(date=lambda x: pd.to_datetime(x['date'])))
    spot_tcfix.set_index('date', inplace=True)
    spot_tcfix = add_vessel_type(spot_tcfix)

    # 增量合并本地 csv
    file_path = 'timecharter.csv'
    if os.path.exists(file_path):
        spot_old = pd.read_csv(file_path, parse_dates=['date']).set_index('date')
        if 'VESSEL TYPE' not in spot_old.columns:
            spot_old = add_vessel_type(spot_old)
        last_date = spot_old.index.max()
        new_data = spot_tcfix[spot_tcfix.index > last_date]
        spot = pd.concat([spot_old, new_data]) if not new_data.empty else spot_old
    else:
        spot = spot_tcfix

    spot = spot.reset_index().drop_duplicates(subset=['date', 'shipName'], keep='last').set_index('date').sort_index()
    spot.to_csv(file_path, index_label='date')

    if DEBUG:
        print(f'[DEBUG] load_tc_data 完成 | 返回长度 = {len(spot)}')
    return spot

# ----------------------------  5. 页面主流程  ----------------------------
days_back = 15 if st.session_state.pop('force_15_days', None) else 2
if DEBUG:
    print(f'[DEBUG] 页面主流程 | days_back = {days_back}')

tc_spot = load_tc_data(days_back)
if tc_spot is None:
    st.warning('⚠️ TC 数据为 None，请查看日志')
else:
    if 'tc_spot' not in st.session_state:
        st.session_state['tc_spot'] = tc_spot
        st.success(f'TC 数据已加载，共 {len(tc_spot)} 条')

# ----------------------------  6. 手动更新按钮  ----------------------------
def update_data():
    st.cache_data.clear()
    st.session_state['force_15_days'] = True
    st.rerun()

st.button('Update Data', on_click=update_data)
st.text('Data will be updated when streamlit is opened')
st.text('If you would like to trigger the reload right now, please click on the above "Update Data" button.')
