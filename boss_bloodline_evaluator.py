class BossBloodlineEvaluator:
    def __init__(self):
        self.speed_sires = {'アルアイン', 'ディープインパクト', 'キズナ', 'コントレイル', 'リアルスティール', 'サトノアラジン', 'シルバーステート', 'ロードカナロア', 'エピファネイア', 'ドゥラメンテ', 'キタサンブラック', 'スワーヴリチャード', 'ダイワメジャー', 'アドマイヤマーズ', 'サートゥルナーリア', 'リオンディーズ', 'レイデオロ', 'モーリス', 'ダノンキングリー'}
        self.tough_sires = {'ゴールドシップ', 'オルフェーヴル', 'ハービンジャー', 'ルーラーシップ', 'サトノダイヤモンド', 'ブラックタイド', 'ジャスタウェイ', 'フィエールマン', 'スクリーンヒーロー', 'バゴ', 'ノヴェリスト', 'サトノクラウン'}
        self.dirt_sires = {'ドレフォン', 'ヘニーヒューズ', 'シニスターミニスター', 'マジェスティックウォリアー', 'ナダル', 'パイロ', 'ルヴァンスレーヴ', 'クリソベリル', 'ニューイヤーズデイ', 'ホッコータルマエ', 'コパノリッキー', 'ゴールドドリーム', 'モーニン', 'マクフィ'}
        self.bms_speed = {'キングカメハメハ', 'ディープインパクト', 'ダイワメジャー', 'クロフネ', 'フジキセキ', 'サクラバクシンオー', 'アドマイヤムーン', 'ロードカナロア', 'Dubawi'}
        self.bms_stamina = {'ハーツクライ', 'ステイゴールド', 'シンボリクリスエス', 'マンハッタンカフェ', 'ゼンノロブロイ', 'ネオユニヴァース', 'ルーラーシップ', 'Galileo', 'Sadler'}

    def evaluate(self, sire, bms, shiba_da, distance, actual_bias):
        sire, bms, b_str = str(sire).strip(), str(bms).strip(), str(actual_bias)
        score, reasons = 0, []
        is_fast = any(k in b_str for k in ('高速', '水捌け', '内先行'))
        is_tough = any(k in b_str for k in ('タフ', '外差し', '重', '不良', 'パワー'))
        if shiba_da == 1:
            if is_fast:
                if any(s in sire for s in self.speed_sires):
                    score += 3; reasons.append(f"父{sire}(水捌け良好・高速持続合致)")
                elif any(s in sire for s in self.tough_sires):
                    score += 0; reasons.append(f"父{sire}(重厚型のため高速馬場割引)")
                if any(b in bms for b in self.bms_speed):
                    score += 2; reasons.append(f"母父{bms}(高速スピード補強)")
                elif any(b in bms for b in self.bms_stamina):
                    score += 1; reasons.append(f"母父{bms}(底力補強)")
            elif is_tough:
                if any(s in sire for s in self.tough_sires):
                    score += 3; reasons.append(f"父{sire}(タフ・持続力合致)")
                elif any(s in sire for s in self.speed_sires):
                    score += 1; reasons.append(f"父{sire}(芝標準適性)")
                if any(b in bms for b in self.bms_stamina):
                    score += 2; reasons.append(f"母父{bms}(タフ底力補強)")
            else:
                if any(s in sire for s in self.speed_sires) or any(s in sire for s in self.tough_sires):
                    score += 2; reasons.append(f"父{sire}(芝王道適性)")
                if any(b in bms for b in self.bms_speed) or any(b in bms for b in self.bms_stamina):
                    score += 2; reasons.append(f"母父{bms}(底力補強)")
        else:
            if any(s in sire for s in self.dirt_sires):
                score += 3; reasons.append(f"父{sire}(ダート適性合致)")
            if any(b in bms for b in self.bms_speed):
                score += 2; reasons.append(f"母父{bms}(砂適性補強)")
        rk = 'S' if score >= 5 else ('A' if score >= 3 else ('B' if score >= 1 else ('C' if score >= -1 else 'D')))
        return rk, (" / ".join(reasons) if reasons else "標準血統構成")
