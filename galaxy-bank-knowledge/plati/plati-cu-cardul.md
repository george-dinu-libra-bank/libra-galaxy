---
banca: Galaxy Bank
limba: ro
categorie: plati
subcategorie: plati-cu-cardul
tip_document: procedură
versiune: 1.0
data_actualizare: 2026-08-19
---
# Plăți cu cardul

## Flux

1. Clientul inițiază plata la comerciant.
2. Se verifică datele cardului și autentificarea suplimentară, dacă este necesară.
3. Banca autorizează sau respinge tranzacția.
4. Tranzacția poate apărea inițial ca sumă rezervată.
5. Decontarea poate avea loc ulterior.

## Limite

Pentru cardurile de debit se aplică limitele zilnice din `carduri/limite-card.md`. Galaxy Credit este limitat de plafonul de credit aprobat, iar retragerile cash sunt limitate la 5.000 RON/zi.

## Tranzacție necunoscută

Blochează cardul și sună la 0800 970 501. Apoi inițiază contestația, dacă tranzacția nu este recunoscută.

## Sume rezervate

O sumă rezervată nu înseamnă neapărat o tranzacție finalizată. Clientul trebuie să evite plata repetată până la clarificarea statusului.
