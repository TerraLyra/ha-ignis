# Egyeki közlemény: archívumos próba (0.20.0)

Forrás: **BM Országos Katasztrófavédelmi Főigazgatóság (BM OKF)**,
[Eddig hét hektár égett le Egyeknél](https://www.katasztrofavedelem.hu/modules/vesz/esemeny/91803).
Megjelenés: 2026. szeptember 9. 14:21 CEST. RSS-mentés: 19:51:25 UTC.

## Importálás

1. Frissíts 0.20.0-ra, majd indítsd újra a Home Assistantot.
2. Fejlesztői eszközök → Műveletek → YAML mód: másold be az
   [importpéldát](../examples/egyek-report-import.yaml), majd futtasd.
3. A válasz `status: archived`. A naptár következő frissítésekor megjelenik
   a szeptember 9-i közlemény, `manual_import` eredetjelöléssel.

Az import csak a hírarchívumot módosítja. A hír nem új tűzészlelés.
Az eredeti megjelenési időt ne írd át: a 30 napos időablakon túli import
elutasításra kerül. A példát a rendszer nem importálja automatikusan.

## Kézi párosítás

A `terralyra_ignis.review_official_report` műveletben válaszd az IGNIS
konfigurációt, add meg a fenti eredeti URL-t, és erősítsd meg, hogy tűzhírt
vizsgálsz. A korábban kézzel ellenőrzött hivatalos eseményoldal pontja:

- Szélesség: `47.61705258844659`
- Hosszúság: `21.002554893493656`
- Feltételezett helybizonytalanság: `5` km; ez **nem szolgáltatói pontosságadat**.
- Kézzel felülvizsgált tág időablak: `2026-09-08T00:00:00+02:00` –
  `2026-09-09T14:21:00+02:00`. Nem pontos gyulladási/kialvási idő.

Az automatikus helyi teszt a korábban HA-ban ellenőrzött hajnali és nappali
észlelési mintával 0,639 és 1,004 km-es `possible` találatokat ad.
A tesztazonosítók mesterségesek; az éles eredmény az adott HA-ban még
megőrzött incident history-tól függ. Csak megjelenési idővel a nappali
minta illeszkedik, a hajnali a 6 órás tolerancián kívül esik.

A művelet nem írja át és nem vonja össze a műholdas eseményeket. A cím
hét hektárt, a szöveg korábban ötven hektárt említ; ezt a forrásbeli
eltérést megőrizzük, nem használjuk párosítási bizonyítékként.

## Archívumkorlátok

Legfeljebb 1000 közlemény, a megjelenéstől 30 napig, helyi HA-tárolóban.
Az újraindítás nem törli; az időkorlát és méretkorlát ellenőrzése hozzáféréskor
történik. A korábban nem letöltött hírek nem kerülnek bele visszamenőleg.
RSS-kieséskor a mentett hírek olvashatók, a feed állapota külön jelenik meg.
