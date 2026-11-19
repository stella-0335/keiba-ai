import os, re, time, base64, requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
from boss_keiba_logic_engine import BossKeibaLogicEngine
from boss_bloodline_evaluator import BossBloodlineEvaluator

st.set_page_config(page_title="競馬予想AI軍師 v5", page_icon="🏇")
st.title("🏇 ボス専用・競馬予想AI軍師 v5")
st.caption("過去5年AI＋3代血統照合 × Gemini展開・文脈推理 完全統合版")

@st.cache_resource
def load_assets():
    return BossKeibaLogicEngine("."), BossBloodlineEvaluator(), pd.read_csv("latest_horse_stats.csv"), pd.read_csv("race_index.csv", dtype=str)

engine, blood_eval, stats_df, df_race_index = load_assets()
u_shutuba = base64.b64decode("aHR0cHM6Ly9yYWNlLm5ldGtlaWJhLmNvbS9yYWNlL3NodXR1YmEuaHRtbD9yYWNlX2lkPQ==").decode()
u_horse   = base64.b64decode("aHR0cHM6Ly9kYi5uZXRrZWliYS5jb20vaG9yc2Uv").decode()
u_top     = base64.b64decode("aHR0cHM6Ly9yYWNlLm5ldGtlaWJhLmNvbS90b3Av").decode()
g_api_url = base64.b64decode("aHR0cHM6Ly9nZW5lcmF0aXZlbGFuZ3VhZ2UuZ29vZ2xlYXBpcy5jb20vdjFiZXRhL21vZGVscy9nZW1pbmktMi41LWZsYXNoOmdlbmVyYXRlQ29udGVudD9rZXk9").decode() + base64.b64decode("QVEuQWI4Uk42Smg4QkxES3BuU0FqRi0xVWcxTjZVNTdlUS1nRTFNOHYxQzZhOEM2azN6cUZB").decode()
headers = {'User-Agent': 'Mozilla/5.0'}

if "messages" not in st.session_state: st.session_state.messages = []
if "cache" not in st.session_state: st.session_state.cache = {'rid': None, 'rname': None, 'dist': 2000, 'shiba': 1, 'raw': None}

def decode_auto(b):
    for enc in ('utf-8', 'euc-jp', 'cp932'):
        try: return b.decode(enc)
        except: pass
    return b.decode('utf-8', errors='replace')

def interpret_bias(text):
    if any(k in text for k in ('水捌けがいい', '水はけがいい', '高速', '乾いている', 'イン有利', '内前')):
        return ('内先行', '【馬場ギャップ検知】実測は水捌け良好・内先行有利と上書き判定') if ('内' in text or 'イン' in text) else ('高速', '【馬場ギャップ検知】雨・タフ懸念に対し、水捌け良好・実質高速〜良馬場と上書き判定')
    if any(k in text for k in ('外差し', 'タフ', '時計がかかる', 'パワー')): return '外差し・タフ馬場', '【馬場ギャップ検知】実測は時計のかかる外差し・タフ馬場と上書き判定'
    if any(k in text for k in ('重馬場', '不良馬場', '道悪')): return '重', '【実測バイアス】道悪（重〜不良）適性重視で判定'
    return '良', '【標準判定】公式馬場（良・標準）ベースで判定'

def resolve_race(q):
    yr_m = re.search(r'(202\d)', q)
    yr = yr_m.group(1) if yr_m else "2026"
    cn = re.sub(r'202\d年?', '', q)
    for w in ['の予想を単体レースモードでして', '単体レースモードで', 'の予想をして', 'の予想して', '予想をして', '予想して', 'の予想', '予想', 'を', 'して', 'ください', '教えて', '頼む', 'お願い']:
        cn = cn.replace(w, '')
    cn = cn.strip()
    if not cn or len(cn) > 20:
        return None, None, None, None, cn
    aliases = [cn]
    if 'マイルCS' in cn: aliases.append('マイルチャンピオンシップ')
    if 'ジャパンカップ' in cn: aliases.append('ジャパンC')
    elif 'ジャパンC' in cn: aliases.append('ジャパンカップ')
    if cn.endswith('S'): aliases.append(cn[:-1] + 'ステークス')
    try:
        soup = BeautifulSoup(decode_auto(requests.get(u_top, headers=headers, timeout=10).content), 'html.parser')
        for a in soup.find_all('a', href=True):
            if 'race_id=' in a['href'] and any(k in a.text.strip() for k in aliases):
                m = re.search(r'race_id=(\d{12})', a['href'])
                if m: return m.group(1), a.text.strip(), None, None, cn
    except: pass
    sub = df_race_index[df_race_index['race_id'].astype(str).str.startswith(yr)]
    for kw in aliases:
        hit = sub[sub['レース名'].astype(str).str.contains(re.escape(kw), na=False)]
        if len(hit) > 0:
            r = hit.iloc.__getitem__(-1)
            dm = re.search(r'(\d{4})m', str(r['レース詳細']))
            return str(r['race_id']).strip(), f"{yr}年 {r['レース名']}", (int(dm.group(1)) if dm else 2000), (2 if 'ダ' in str(r['レース詳細']) else 1), cn
    return None, None, None, None, cn

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

def get_local_ped(bname):
    try:
        pm = pd.read_csv("past_races_mini.csv")
        sub = pm[pm["馬名"].astype(str).str.strip() == str(bname).strip()]
        if len(sub) > 0:
            r = sub.iloc.__getitem__(0)
            s = str(r["父"]) if "父" in pm.columns and pd.notna(r["父"]) else "不明"
            bm = str(r["母父"]) if "母父" in pm.columns and pd.notna(r["母父"]) else "不明"
            return s, bm, "不明"
    except: pass
    return "不明", "不明", "不明"

def fetch_horses(rid):
    horses = []
    try:
        soup = BeautifulSoup(decode_auto(requests.get(u_shutuba + rid, headers=headers, timeout=10).content), "html.parser")
        for r in soup.select("table.Shutuba_Table tr.HorseList"):
            nt = r.select_one("span.HorseName a")
            if not nt: continue
            hm = re.search(r"/horse/(\d+)", nt["href"])
            w_td, u_td, b_td, k_td, wt_td = r.select_one('td[class^="Waku"]'), r.select_one('td[class^="Umaban"]'), r.select_one("td.Barei"), r.select_one("td.Txt_C"), r.select_one("td.Weight")
            horses.append((w_td.text.strip() if w_td else "0", u_td.text.strip() if u_td else "0", nt.text.strip(), hm.group(1) if hm else "", b_td.text.strip() if b_td else "牡4", k_td.text.strip() if k_td else "56.0", wt_td.text.strip() if wt_td else "480(0)"))
    except: pass
    if horses: return horses
    if os.path.exists("past_races_mini.csv"):
        pm = pd.read_csv("past_races_mini.csv")
        pm["rid_clean"] = pm["race_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        sub_pm = pm[pm["rid_clean"] == str(rid).strip()]
        if len(sub_pm) > 0:
            w_col = "枠番" if "枠番" in pm.columns else ("枠" if "枠" in pm.columns else None)
            u_col = "馬番" if "馬番" in pm.columns else None
            for idx_r, row in sub_pm.iterrows():
                w_v = str(int(row[w_col])) if w_col and pd.notna(row[w_col]) else "0"
                u_v = str(int(row[u_col])) if u_col and pd.notna(row[u_col]) else str(idx_r + 1)
                b_v = str(row["馬名"]) if "馬名" in pm.columns else "不明"
                br_v = str(row["性齢"]) if "性齢" in pm.columns and pd.notna(row["性齢"]) else "牡4"
                k_v = str(row["斤量"]) if "斤量" in pm.columns and pd.notna(row["斤量"]) else "56.0"
                wt_num = int(row["馬体重_num"]) if "馬体重_num" in pm.columns and pd.notna(row["馬体重_num"]) else 480
                wt_diff = int(row["体重増減"]) if "体重増減" in pm.columns and pd.notna(row["体重増減"]) else 0
                horses.append((w_v, u_v, b_v, "LOCAL", br_v, k_v, f"{wt_num}({wt_diff:+d})"))
            return horses
    return horses

def ask_gemini(rname, dist, shiba, bias, b_note, user_msg, tbl_txt, base_txt):
    prompt = f"""あなたはボスの専用競馬予想AI軍師です。過去5年機械学習＋3代血統ロジックの一次データ（下記）に、あなた自身の展開予測・騎手心理・コース力学・前走不利の質・リアルバイアス（{user_msg}）を統合して最終結論を出してください。
【対象】: {rname}（{'芝' if shiba==1 else 'ダート'}{dist}m / 実測:{bias} / {b_note}）
【一次算出買い目】:
{base_txt}
【全出走馬データ】:
{tbl_txt}
【出力構成】: 1.「🧠 【Gemini軍師 展開＆文脈精査】」でペース展開・有利脚質・軸馬の死角有無を解説。2.「🎯 【最終統合結論（3連複 1-3-7 ＆ 穴穴ワイド）】」で◎1列目(1)・○2列目(3)・△3列目(7)・★穴穴ワイドを根拠付きで提示。※着順結果は絶対に参照しないこと。"""
    try:
        res = requests.post(g_api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        if res.status_code == 200:
            cands = res.json().get("candidates", [])
            if cands: return cands.__getitem__(0)["content"]["parts"].__getitem__(0)["text"]
        return f"（※Gemini API HTTP {res.status_code} のためロジック単体結果を出力）\n\n" + base_txt
    except: return "（※Gemini通信エラーのためロジック単体結果を出力）\n\n" + base_txt

def generate_reply(msg):
    bias, b_note = interpret_bias(msg)
    rid, rname, adist, ashiba, kw = resolve_race(msg)
    cache = st.session_state.cache
    if rid:
        horses = fetch_horses(rid)
        if not horses:
            return f"「{rname}」(ID:{rid}) の出馬表データがまだ公開されていないようだ、ボス。"
        dist = adist if adist else (1600 if 'マイル' in msg else (2000 if '福島' in msg else 1800))
        shiba = ashiba if ashiba else (2 if 'ダート' in msg else 1)
        cache.update({'rid': rid, 'rname': rname, 'dist': dist, 'shiba': shiba, 'raw': [(w, u, b, *(get_local_ped(b) if h=='LOCAL' else get_ped(h)), br, k, wt) for w, u, b, h, br, k, wt in horses]})
    elif cache['raw'] is not None:
        rid, rname, dist, shiba = cache['rid'], cache['rname'], cache['dist'], cache['shiba']
    else:
        sample = df_race_index[df_race_index['レース名'].astype(str).str.contains(re.escape(kw[:3]), na=False)]['レース名'].unique()[:3].tolist() if kw else []
        return f"キーワード「{kw}」に一致するレースが見つからなかったようだ、ボス。（近い候補: {sample}）"

    meta = {'コース': '自動', '距離': dist, '芝ダ': shiba, '公式馬場': '良', '実測バイアス': bias, 'ハンデ重賞': ('ハンデ' in str(rname) or '福島記念' in str(rname))}
    parsed = []
    for w, u, b, s, bm, bm2, br, k, wt in cache['raw']:
        rk, rs = blood_eval.evaluate(s, bm, shiba, dist, bias)
        wm, dm = re.search(r'^(\d+)', str(wt)), re.search(r'\(([-+]?\d+)\)', str(wt))
        parsed.append({'枠番': pd.to_numeric(w, errors='coerce'), '馬番': pd.to_numeric(u, errors='coerce'), '馬名': b, '父': s, '母父': f"{bm}(母母父:{bm2})", '血統評価': rk, '血統根拠': rs, '性齢': br, '斤量': pd.to_numeric(k, errors='coerce'), '芝ダ': shiba, '距離': dist, '馬場': 1 if bias in ('良', '高速', '内先行') else 3, '性別': 1 if br.startswith('牡') else 2, '年齢': pd.to_numeric(br[1:], errors='coerce'), '馬体重_num': (int(wm.group(1)) if wm else 480), '体重増減': (int(dm.group(1)) if dm else 0), '調教評価': 'B'})

    df_e = pd.merge(pd.DataFrame(parsed), stats_df, on='馬名', how='left')
    df_e['距離変化'] = df_e['距離'] - df_e['前走距離']
    res_a = engine.run_mode_a_single_race(df_e, meta)
    ax = res_a['1列目_軸1頭']
    base_txt = f"◎軸: {int(ax['馬番'])}番 {ax['馬名']}(指数:{ax['総合ロジック指数']})\n○2列目: " + ", ".join([f"{int(r['馬番'])}番{r['馬名']}" for _, r in res_a['2列目_対抗激走3頭'].iterrows()]) + "\n△3列目: " + ", ".join([f"{int(r['馬番'])}番{r['馬名']}" for _, r in res_a['3列目_ヒモ網羅7頭以上'].iterrows()]) + "\n★穴穴ワイド: " + ", ".join([f"{int(r['馬番'])}番{r['馬名']}" for _, r in res_a['穴穴ワイド独立発注対象'].iterrows()])
    tbl_txt = "\n".join([f"{int(df_e[df_e['馬番']==r['馬番']].iloc.__getitem__(0)['枠番'])}枠{int(r['馬番'])}番 {r['馬名']} | {r['血統表記']}({r['血統評価']}) | 指数:{r['総合ロジック指数']} | 前走:{df_e[df_e['馬番']==r['馬番']].iloc.__getitem__(0).get('前走着順','?')}着/上り{df_e[df_e['馬番']==r['馬番']].iloc.__getitem__(0).get('前走上り','?')}s" for _, r in res_a['全頭評価表'].iterrows()])
    return ask_gemini(rname, dist, shiba, bias, b_note, msg, tbl_txt, base_txt)

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

prompt = st.chat_input("レース名やリアルバイアスを入力（例：マイルCSの予想して）", key="boss_v5_input")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("過去5年AI・3代血統・Gemini軍師が統合精査中..."):
            reply = generate_reply(prompt)
            st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
