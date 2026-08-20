from dataclasses import dataclass
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.infrastructure.config import Settings, get_settings
from app.infrastructure.supabase import create_auth_client, create_user_client


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: UUID
    access_token: str


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lipseste tokenul de autentificare.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    token = _bearer_token(authorization)
    client = create_auth_client(settings)

    try:
        response = await to_thread.run_sync(client.auth.get_user, token)
        user = response.user
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesiunea este invalida sau a expirat.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizator invalid.")

    return UserContext(user_id=UUID(str(user.id)), access_token=token)


def get_user_supabase(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Client:
    return create_user_client(settings, user.access_token)


async def cere_administrator(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> UserContext:
    """Lasa sa treaca numai administratorii.

    Verificarea intreaba baza de date, nu tokenul: rolul sta in profiles si e
    inghetat de trigger, deci nu poate fi ridicat din aplicatie. Un rol pus in
    JWT ar fi mai ieftin de citit, dar ar ramane valabil pana expira tokenul,
    inclusiv dupa ce i-a fost luat cuiva dreptul.

    Chiar daca cineva ar ocoli verificarea de aici, RLS ramane bariera reala:
    politicile de la 0004 cer public.este_administrator() in baza de date.
    """

    def interogare() -> str | None:
        raspuns = (
            client.table("profiles")
            .select("rol")
            .eq("id", str(user.user_id))
            .maybe_single()
            .execute()
        )
        date = raspuns.data if raspuns else None
        return date.get("rol") if date else None

    try:
        rol = await to_thread.run_sync(interogare)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nu am putut verifica drepturile contului.",
        ) from exc

    if rol != "administrator":
        # Acelasi raspuns si cand contul nu exista, si cand exista dar e client:
        # cine incearca ruta nu trebuie sa afle ce a nimerit.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceasta zona e disponibila numai administratorilor.",
        )

    return user
