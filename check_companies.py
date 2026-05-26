import csv

with open("data/articles.csv", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

no_company = [r for r in rows if not r.get("企業名", "").strip()]
print(f"企業名なし: {len(no_company)} / 全体: {len(rows)} 件\n")
for r in no_company:
    date = r["収集日時(UTC)"]
    title = r["タイトル"][:65]
    print(f"  [{date}] {title}")
