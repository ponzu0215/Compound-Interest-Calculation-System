# 投資複利計算システム（Streamlit版）

元HTML「資産複利計算ツール.html」を Streamlit + Python に移植したWebアプリです。

## 起動（ローカル）
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 公開（Streamlit Community Cloud）
1. このフォルダ一式を GitHub リポジトリに配置（Public推奨）
2. Streamlit Community Cloud で New app
   - Repository: あなたのrepo
   - Branch: main
   - Main file: app.py
3. Deploy

## 仕様メモ
- ①/②は「月初積立（期首払い）」の前提（元HTMLの注意書き通り）
- ③は「月末取り崩し（期末払い）」の前提
- 税金モデルは元HTMLの簡易モデルをそのまま移植
