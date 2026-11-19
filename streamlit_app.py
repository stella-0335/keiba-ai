import os, re, time, base64, requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
from boss_keiba_logic_engine import BossKeibaLogicEngine
from boss_bloodline_evaluator import BossBloodlineEvaluator

st.set_page_config(page_title="競馬予想AI軍師 v3", page_icon="🏇")
st.title("🏇 ボス専用・競馬予想AI軍師 v3")
st.caption("過去5年機械学習＋3代血統照合＋馬場ギャップ対応（常駐版）")

@st.cache_resource
def load_assets():
    return BossKeibaLogicEngine("."), BossBloodlineEvaluator(), pd.read_csv("latest_horse_stats.csv"), pd.read_csv("race_index.csv", dtype={'race_id': str})

engine, blood_eval, stats_df, df_race_index = load_assets()
u_shutuba = base64.b64decode("aHR0cHM6Ly9yYWNlLm5ldGtlaWJhLmNvbS9yYWNlL3NodXR1YmEuaHRtbD9yYWNlX2lkPQ==").decode()
u_db_race = base64.b64decode("aHR0cHM6Ly9kYi5uZXRrZWliYS5jb20vcmFjZS8=").decode()
u_horse   = base64.b64decode("aHR0cHM6Ly9kYi5uZXRrZWliYS5jb20vaG9yc2Uv").decode()
u_top     = base64.b64decode("aHR0cHM6Ly9yYWNlLm5ldGtlaWJhLmNvbS90b3Av").decode()
headers = {'User-Agent': 'Mozilla/5.0'}

if "messages" not in st.session_state: st.session_state.messages = []
if "cache" not in st.session_state: st.session_state.cache = {'rid': None, 'rname': None, 'dist': 2000, 'shiba': 1, 'raw': None}

def decode_auto(b):
    try: return b.decode('utf-8')
    except: return b.decode('euc-jp', errors='replace')

def interpret_bias(text):
    if any(k in text for k in ('水捌けがいい', '水はけがいい', '高速', '乾いている', 'イン有利', '内前')):
        return ('内先行', '【馬場ギャップ検知】実測は水捌け良好・内先行有利と上書き判定') if ('内' in text or 'イン' in text) else ('高速', '【馬場ギャップ検知】雨・タフ懸念に対し、水捌け良好・実質高速〜良馬場と上書き判定')
    if any(k in text for k in ('外差し', 'タフ', '時計がかかる', 'パワー')): return '外差し・タフ馬場', '【馬場ギャップ検知】実測は時計のかかる外差し・タフ馬場と上書き判定'
    if any(k in text for k in ('重馬場', '不良馬場', '道悪')): return '重', '【実測バイアス】道悪（重〜不良）適性重視で判定'
    return '良', '【標準判定】公式馬場（良・標準）ベースで判定'

def resolve_race(q):
    yr_m = re.search(r'(202\d)', q); yr = yr_m.group(1) if yr_m else "2026"
    cn = re.sub(r'202\d年?', '', q)
    for w in ('単体レースモード', 'WIN5', 'の予想をして', 'を予想して', 'の予想して', 'の予想', '予想して', '精査して', '外差し', 'タフ馬場', '良馬場', '高速馬場', '重馬場', 'で', 'を', ' ', '　'): cn = cn.replace(w, '')
    cn = cn.strip()
    if not cn or len(cn) > 15 or '、' in q or 'が' in q or 'けど' in q: return None, None, None, None
    try:
        soup = BeautifulSoup(decode_auto(requests.get(u_top, headers=headers, timeout=10).content), 'html.parser')
        for a in soup.find_all('a', href=True):
            if 'race_id=' in a['href'] and cn in a.text.strip():
                m = re.search(r'race_id=(\d{12})', a['href'])
                if m: return m.group(1), a.text.strip(), None, None
    except: pass
    sub = df_race_index[df_race_index['race_id'].str.startswith(yr)]
    hit = sub[sub['レース名'].str.contains(re.escape(cn), na=False)]
    if len(hit) > 0:
        r = hit.iloc.__getitem__(-1); dm = re.search(r'(\d{4})m', str(r['レース詳細']))
        return r['race_id'], f"{yr}年 {r['レース名']}", (int(dm.group(1)) if dm else 2000), (2 if 'ダ' in str(r['レース詳細']) else 1)
    return None, None, None, None

def get_ped(hid):
    sire, bms, bms2 = '不明', '不明', '不明'
    if not hid: return sire, bms, bms2
    try:
        hs = BeautifulSoup(decode_auto(requests.get(u_horse + "ped/" + hid + "/", headers=headers, timeout=10).content), 'html.parser')
        r16, r8, r4 = hs.select('table.blood_table td[rowspan="16"]'), hs.select('table.blood_table td[rowspan="8"]'), hs.select('table.blood_table td[rowspan="4"]')
        if len(r16) >= 1: sire = (r16.__getitem__(0).find('a') or r16.__getitem__(0)).text.strip().split('\n').__getitem__(0)
        if len(r8) >= 3: bms = (r8.__getitem__(2).find('a') or r8.__getitem__(2)).text.strip().split('\n').__getitem__(0)
        if len(r4) >= 7: bms2 = (r4.__getitem__(6).find('a') or r4.__getitem__(6)).text.strip().split('\n').__getitem__(0)
    except: pass
    return sire, bms, bms2

def generate_reply(msg):
    bias, b_note = interpret_bias(msg)
    rid, rname, adist, ashiba = resolve_race(msg)
    cache = st.session_state.cache
    if rid:
        soup = BeautifulSoup(decode_auto(requests.get(u_shutuba + rid, headers=headers, timeout=10).content), 'html.parser')
        rows = soup.select('table.Shutuba_Table tr.HorseList')
        horses = []
        if rows:
            for r in rows:
                nt = r.select_one('span.HorseName a'); hm = re.search(r'/horse/(\d+)', nt['href']) if nt else None
                w_td, u_td, b_td, k_td, wt_td = r.select_one('td[class^="Waku"]'), r.select_one('td[class^="Umaban"]'), r.select_one('td.Barei'), r.select_one('td.Txt_C'), r.select_one('td.Weight')
                horses.append((w_td.text.strip() if w_td else '0', u_td.text.strip() if u_td else '0', nt.text.strip() if nt else '', hm.group(1) if hm else '', b_td.text.strip() if b_td else '牡4', k_td.text.strip() if k_td else '56.0', wt_td.text.strip() if wt_td else '480(0)'))
        else:
            tbl = BeautifulSoup(decode_auto(requests.get(u_db_race + rid + "/", headers=headers, timeout=10).content), 'html.parser').find('table', class_='race_table_01')
            if tbl:
                for tr in tbl.find_all('tr')[1:]:
                    tds = tr.find_all('td')
                    if len(tds) >= 15:
                        at = tds.__getitem__(3).find('a'); hm = re.search(r'/horse/(\d+)', at['href']) if at else None
                        horses.append((tds.__getitem__(1).text.strip(), tds.__getitem__(2).text.strip(), (at.text.strip() if at else tds.__getitem__(3).text.strip()), hm.group(1) if hm else '', tds.__getitem__(4).text.strip(), tds.__getitem__(5).text.strip(), tds.__getitem__(14).text.strip()))
        if not horses: return f"「{rname}」の出馬表がまだ公開されていないようだ、ボス。"
        dist = adist if adist else (1600 if 'マイル' in msg else (2000 if '福島' in msg else 1800))
        shiba = ashiba if ashiba else (2 if 'ダート' in msg else 1)
        cache.update({'rid': rid, 'rname': rname, 'dist': dist, 'shiba': shiba, 'raw': [(w, u, b, *get_ped(h), br, k, wt) for w, u, b, h, br, k, wt in horses]})
    elif cache['raw'] is not None: rid, rname, dist, shiba = cache['rid'], cache['rname'], cache['dist'], cache['shiba']
    else: return "まずレース名（例：『マイルCSの予想して』）を送ってくれ、ボス。"

    meta = {'コース': '自動', '距離': dist, '芝ダ': shiba, '公式馬場': '良', '実測バイアス': bias, 'ハンデ重賞': ('ハンデ' in str(rname) or '福島記念' in str(rname))}
    parsed = []
    for w, u, b, s, bm, bm2, br, k, wt in cache['raw']:
        rk, rs = blood_eval.evaluate(s, bm, shiba, dist, bias)
        wm, dm = re.search(r'^(\d+)', str(wt)), re.search(r'\(([-+]?\d+)\)', str(wt))
        parsed.append({'枠番': pd.to_numeric(w, errors='coerce'), '馬番': pd.to_numeric(u, errors='coerce'), '馬名': b, '父': s, '母父': f"{bm}(母母父:{bm2})", '血統評価': rk, '血統根拠': rs, '性齢': br, '斤量': pd.to_numeric(k, errors='coerce'), '芝ダ': shiba, '距離': dist, '馬場': 1 if bias in ('良', '高速', '内先行') else 3, '性別': 1 if br.startswith('牡') else 2, '年齢': pd.to_numeric(br[1:], errors='coerce'), '馬体重_num': (int(wm.group(1)) if wm else 480), '体重増減': (int(dm.group(1)) if dm else 0), '調教評価': 'B'})

    df_e = pd.merge(pd.DataFrame(parsed), stats_df, on='馬名', how='left')
    df_e['距離変化'] = df_e['距離'] - df_e['前走距離']
    res_a = engine.run_mode_a_single_race(df_e, meta)
    ax = res_a['1列目_軸1頭']; ax_r = df_e[df_e['馬番']==ax['馬番']]['血統根拠'].values.__getitem__(0)

    out = [f"### 🏆 【モードA：単体レースモード v3】({rname})", f"{b_note}", f"**条件**: {'芝' if shiba==1 else 'ダート'}{dist}m / 実測バイアス:**{bias}**\n", f"#### ◎ 1列目：軸（1頭）", f"- **{int(ax['馬番'])}番 {ax['馬名']}**（{ax['血統表記']}）｜評価:**{ax['血統評価']}**｜指数:**{ax['総合ロジック指数']}**", f"  - 根拠: {ax_r} / {ax['加点・激走根拠']}（減点:{ax['減点要因']}）\n", f"#### ○ 2列目：対抗・激走枠（3頭）"]
    for _, rw in res_a['2列目_対抗激走3頭'].iterrows():
        br = df_e[df_e['馬番']==rw['馬番']]['血統根拠'].values.__getitem__(0)
        out.append(f"- **{int(rw['馬番'])}番 {rw['馬名']}**（{rw['血統表記']}）｜評価:**{rw['血統評価']}**｜指数:{rw['総合ロジック指数']}（{br} / {rw['加点・激走根拠']}）")
    out.append("\n#### △ 3列目：ヒモ網羅枠（7頭〜）")
    for _, rw in res_a['3列目_ヒモ網羅7頭以上'].iterrows(): out.append(f"- **{int(rw['馬番'])}番 {rw['馬名']}**（{rw['血統表記']}）｜評価:{rw['血統評価']}｜指数:{rw['総合ロジック指数']}")
    out.append("\n#### ★ 穴穴ワイド独立発注対象")
    for _, rw in res_a['穴穴ワイド独立発注対象'].iterrows(): out.append(f"- **{int(rw['馬番'])}番 {rw['馬名']}**（{rw['血統表記']}）")
    return "\n".join(out)

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("レース名やリアルバイアスを入力（例：マイルCSの予想して）"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("一次データ・3代血統・過去5年AIを精査中..."):
            reply = generate_reply(prompt)
            st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
