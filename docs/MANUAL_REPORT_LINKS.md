# Kézzel jóváhagyott hírkapcsolatok ellenőrzése

Ez a funkció még kiadatlan fejlesztés. Telepített változatban csak a kiadás után használható.

1. Az `terralyra_ignis.review_official_report` művelettel kérj friss jelöltlistát.
   A koordináták a tűz feltételezett helyét jelöljék, ne a tűzoltóság székhelyét.
   Az időablak kézzel ellenőrzött feltételezés; a közzététel nem a tűz kezdete.
2. Minden jelöltnél külön nézd meg a koordinátákat, távolságot, `first_seen` /
   `last_seen` időpontokat, forrásokat és a bizonytalanság indokait.
3. Csak a kiválasztott jelöltet mentsd a `save_official_report_link` művelettel.
   Másold át az eredeti ellenőrzés összes bemenetét, a jelölt `incident_id` és
   `review_token` mezőjét; a `confirm_fire_report` és `confirm_association` legyen
   tudatosan jóváhagyva. Ne másold át más jelölt tokenjét.
4. A `list_official_report_links` művelettel ellenőrizd a mentést. A `status: active`
   azt jelenti, hogy a hivatkozott adatok még megvannak, nem azt, hogy a tűz aktív.
5. Frissítsd a naptárnézetet. A hír és a műholdas esemény leírásában jelenjen meg
   a kézi kapcsolat, a BM OKF hivatkozás, az ellenőrzés ideje és a kapcsolat ID-je.
   Az eredeti időpontok, forráslista és eseményszám maradjon változatlan.
6. A `remove_official_report_link` műveletben add meg a konfiguráció és a kapcsolat
   azonosítóját. Frissítés után mindkét naptárból csak a kapcsolat jelölése tűnjön el;
   a hír és a műholdas esemény maradjon meg.

## Biztonsági ellenőrzések

- Hiányzó jóváhagyással, másik jelölt tokenjével vagy megváltoztatott bemenettel
  ne lehessen menteni. Megváltozott jelöltnél új ellenőrzés szükséges.
- Újraindítás után a mentett kapcsolat és ellenőrzési adatai maradjanak meg.
- Másik IGNIS konfigurációból ne lehessen listázni vagy törölni ezt a kapcsolatot.
- Lejárt hírhez ne lehessen menteni. A kapcsolatok legfeljebb a közzétételtől
  számított 30 napig tárolódnak. A törlés az archívum következő használatakor történik.
- A hiányzó vagy módosult hír/esemény kapcsolata ne jelenjen meg érvényesként.
- A `possible` minősítés kézi jóváhagyáskor is maradjon `possible`.

## Egyek

A helyi, éles ellenőrzés három közeli jelöltet adott egy szándékosan tág,
szeptember 8–9-i időablakban. Ezek nem három bizonyítottan külön tűzesetet jelentenek,
és nem szabad őket egyszerre automatikusan elfogadni. Az éles incident ID-ket és
tokeneket mindig az adott telepítés friss ellenőrzéséből kell választani.
A mentett BM OKF hír közzétételi ideje 2026-09-09 14:21 CEST; a szövegben említett
előző esti tűzkezdet nem azonos ezzel az időponttal.
