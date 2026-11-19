import pandas as pd, numpy as np, pickle, os

class BossKeibaLogicEngine:
    def __init__(self, save_dir='/content/drive/MyDrive/Keiba_AI_AllRaces'):
        m_path = os.path.join(save_dir, 'keiba_ai_model_v2.pkl')
        self.model = pickle.load(open(m_path, 'rb')) if os.path.exists(m_path) else None

    def calculate_base_ai_score(self, df):
        df = df.copy()
        feats = ['芝ダ', '距離', '馬場', '枠番', '馬番', '性別', '年齢', '斤量', '騎手コード', '馬体重_num', '体重増減', '前走着順', '前走上り', '前走人気', '前走オッズ', '距離変化']
        df_u = df.copy(); df_u['騎手コード'] = 0
        for c in feats:
            if c not in df_u.columns: df_u[c] = 0
        df['AI基礎適性値'] = (self.model.predict_proba(df_u[feats])[:, 1] * 100).round(2) if self.model is not None else 50.0
        return df

    def evaluate_4_steps(self, df, race_meta):
        df = self.calculate_base_ai_score(df)
        b_actual = race_meta.get('実測バイアス', race_meta.get('公式馬場', '良'))
        results = []
        for _, row in df.iterrows():
            score = row['AI基礎適性値']
            deducts, bonuses = [], []
            b_rank = row.get('血統評価', 'B')
            score += {'S': 22.0, 'A': 14.0, 'B': 4.0, 'C': -10.0, 'D': -22.0}.get(b_rank, 0.0)
            w_diff = row.get('体重増減', 0)
            if w_diff <= -10: score -= 15.0; deducts.append(f"大幅馬体減({w_diff}kg)")
            elif w_diff <= -6: score -= 7.0; deducts.append(f"馬体減({w_diff}kg)")
            elif w_diff >= 12: score -= 6.0; deducts.append(f"大幅馬体増(+{w_diff}kg)")
            if row.get('斤量', 55.0) >= 58.0: score -= 6.0; deducts.append(f"重斤量({row.get('斤量')}kg)")
            p_agari = row.get('前走上り', 99.0)
            if pd.notna(p_agari) and p_agari <= 33.8: score += 9.0; bonuses.append(f"前走上り最速級({p_agari}s)")
            elif pd.notna(p_agari) and p_agari <= 34.4: score += 4.5; bonuses.append(f"前走上り優秀({p_agari}s)")
            p_rank = row.get('前走着順', 99)
            if pd.notna(p_rank) and p_rank >= 8:
                if pd.notna(p_agari) and p_agari <= 34.5: score += 7.0; bonuses.append("前走着順外も末脚確実")
                else: score -= 4.0; deducts.append(f"前走敗戦({int(p_rank)}着)")
            waku = row.get('枠番', 4)
            if '高速' in b_actual or '内先行' in b_actual:
                if waku >= 7: score -= 5.0; deducts.append(f"外枠ロス懸念({int(waku)}枠)")
                elif waku <= 4: score += 5.0; bonuses.append(f"内〜中枠立ち回り優位({int(waku)}枠)")
            elif '外差し' in b_actual and waku >= 6:
                score += 8.0; bonuses.append(f"外差しバイアス合致({int(waku)}枠)")
            is_ra = (len(deducts) == 0) and (b_rank in ('S', 'A'))
            ana_pot = score + (10.0 if (pd.notna(p_agari) and p_agari <= 34.5) else 0.0) + (8.0 if b_rank in ('S', 'A', 'B') else 0.0)
            results.append({'馬番': row.get('馬番', 0), '馬名': row.get('馬名', ''), '血統表記': f"{row.get('父', '不明')}×{row.get('母父', '不明')}", '血統評価': b_rank, '総合ロジック指数': round(score, 2), '激走穴ポテンシャル': round(ana_pot, 2), 'ルート判定': 'ルートA(死角なし)' if is_ra else 'ルートB(死角あり)', '減点要因': ', '.join(deducts) if deducts else 'なし', '加点・激走根拠': ', '.join(bonuses) if bonuses else '標準'})
        return pd.DataFrame(results).sort_values('総合ロジック指数', ascending=False).reset_index(drop=True), (race_meta.get('公式馬場', '良') != b_actual)

    def run_mode_a_single_race(self, df, race_meta):
        res_df, gap = self.evaluate_4_steps(df, race_meta)
        ra = res_df[res_df['ルート判定'] == 'ルートA(死角なし)']
        ax = ra.iloc.__getitem__(0) if len(ra) > 0 else res_df.iloc.__getitem__(0)
        oth = res_df[res_df['馬番'] != ax['馬番']].copy()
        geki = oth.iloc[2:].sort_values('激走穴ポテンシャル', ascending=False).head(1)
        col2 = pd.concat([oth.head(2), geki]).drop_duplicates(subset=['馬番'])
        col3 = oth[oth['血統評価'].isin(('S', 'A', 'B'))].head(9)
        if len(col3) < 7: col3 = oth.head(8)
        wides = pd.concat([geki, oth.iloc[2:].sort_values('激走穴ポテンシャル', ascending=False).iloc[1:4]]).drop_duplicates(subset=['馬番'])
        return {'馬場ギャップ検知': gap, '全頭評価表': res_df, '1列目_軸1頭': ax, '2列目_対抗激走3頭': col2, '3列目_ヒモ網羅7頭以上': col3, '穴穴ワイド独立発注対象': wides}
