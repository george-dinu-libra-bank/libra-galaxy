import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status

_LOCK = Lock()
_INCERCARI: dict[str, list[float]] = defaultdict(list)


def limiteaza(cheie: str, max_incercari: int, fereastra_secunde: int) -> None:
    """
    Rate limiter simplu, in memorie — suficient pentru un singur proces
    (dev/MVP). Daca serviciul ruleaza cu mai multe workere/replici, fiecare
    are propria evidenta, deci limita reala e mai mare decat cea configurata;
    pentru productie ar trebui mutat pe un store partajat (ex. Redis).

    Foloseste pentru orice ruta unde userul poate incerca repetat sa
    'ghiceasca' o potrivire (ex. login biometric) — cheia e de obicei
    email+IP, ca sa limitezi atat brute-force pe un cont cat si scanarea
    multor conturi de pe aceeasi masina.
    """
    acum = time.monotonic()
    prag = acum - fereastra_secunde

    with _LOCK:
        incercari = [t for t in _INCERCARI[cheie] if t > prag]

        if len(incercari) >= max_incercari:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"cod": "prea_multe_incercari", "mesaj": "Prea multe incercari. Asteapta putin si reia."},
            )

        incercari.append(acum)
        _INCERCARI[cheie] = incercari
