class ErrorAplicatie(Exception):
    """
    Eroare cu cod stabil, ca raspunsul catre client (si logul din Next.js) sa
    spuna exact ce a picat, nu doar "500 Internal Server Error".

    `cod` e un identificator stabil (folosit de frontend/loguri pentru
    diagnostic), `mesaj` e explicatia, iar `status_http` controleaza codul
    de raspuns (502 = dependinta externa a picat, 422 = input invalid etc).
    """

    def __init__(self, cod: str, mesaj: str, status_http: int = 500):
        self.cod = cod
        self.mesaj = mesaj
        self.status_http = status_http
        super().__init__(f"[{cod}] {mesaj}")


class DescarcareImagineError(ErrorAplicatie):
    def __init__(self, bucket: str, cale: str):
        super().__init__(
            cod="descarcare_imagine_esuata",
            mesaj=f"Nu am putut descarca imaginea din storage ({bucket}/{cale}).",
            status_http=502,
        )


class ScriereRezultatError(ErrorAplicatie):
    def __init__(self):
        super().__init__(
            cod="scriere_rezultat_esuata",
            mesaj="Am comparat fetele, dar nu am putut salva rezultatul in baza de date.",
            status_http=502,
        )
