from app.infrastructure.ocr import extrage_cnp

CNP_VALID = "1970101221144"


def test_extrage_cnp_din_text_fara_potriviri():
    # Bytes invalizi ca imagine -> nu trebuie sa arunce exceptie.
    cnp, incredere = extrage_cnp(b"nu-e-o-imagine")
    assert cnp is None
    assert incredere == 0.0
