"""Contraseñas de las cuentas de Streamlit: PBKDF2 con sal; en los secretos solo va la huella, nunca la clave."""
import hashlib, hmac


def huella(clave: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), 200_000).hex()


def valida(cuentas, usuario: str, clave: str):
    """La empresa de la cuenta si usuario y clave coinciden; si no, None."""
    c = cuentas.get(usuario.strip().lower())
    return c["empresa"] if c and hmac.compare_digest(huella(clave, c["sal"]), c["huella"]) else None
