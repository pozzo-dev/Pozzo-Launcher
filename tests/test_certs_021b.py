"""0.21.0 (W4c): il certificato del server si rifa' con la STESSA chiave (impronta della chiave pubblica stabile);
la CA nuova ha NameConstraints (solo reti locali); le CA vecchie restano come sono."""
from __future__ import annotations

import ssl
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography import x509  # noqa: E402

from pozzo.remote import certs  # noqa: E402


def _spki(crt: Path) -> str:
    return certs.spki_fp(ssl.PEM_cert_to_DER_cert(crt.read_text()))


def test_leaf_regenerated_keeps_key(monkeypatch=None):
    t = Path(tempfile.mkdtemp())
    ips = ["192.168.1.5"]
    orig = certs.lan_ips
    certs.lan_ips = lambda: ips
    try:
        crt, key, _ = certs.ensure(t)
        before_spki, before_pem = _spki(crt), crt.read_text()
        ips.append("172.20.0.1")  # nuovo adattatore (Hyper-V/WSL): il certificato va rifatto
        certs.ensure(t)
        assert crt.read_text() != before_pem, "il certificato doveva essere rifatto"
        assert _spki(crt) == before_spki, "stessa chiave: stessa impronta"
    finally:
        certs.lan_ips = orig


def test_new_ca_has_name_constraints_and_leaf_validates():
    from cryptography.x509 import verification
    t = Path(tempfile.mkdtemp())
    crt, _, ca = certs.ensure(t)
    ca_c = x509.load_pem_x509_certificate(ca.read_bytes())
    nc = ca_c.extensions.get_extension_for_class(x509.NameConstraints)
    assert nc.critical
    leaf = x509.load_pem_x509_certificate(crt.read_bytes())
    store = verification.Store([ca_c])
    b = verification.PolicyBuilder().store(store)
    b.build_server_verifier(x509.DNSName("localhost")).verify(leaf, [])
    b.build_server_verifier(x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1"))).verify(leaf, [])


def test_ca_cannot_sign_foreign_site():
    """Chi ruba ca.key non puo' firmare un sito qualsiasi: il verificatore rifiuta."""
    import datetime as dt

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509 import verification
    from cryptography.x509.oid import NameOID
    t = Path(tempfile.mkdtemp())
    certs.ensure(t)
    ca_cert, ca_key = certs._ca(t)
    pk = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    evil = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "bank.com")]))
            .issuer_name(ca_cert.subject).public_key(pk.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("bank.com")]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    b = verification.PolicyBuilder().store(verification.Store([ca_cert]))
    try:
        b.build_server_verifier(x509.DNSName("bank.com")).verify(evil, [])
    except verification.VerificationError:
        return
    raise AssertionError("la CA ha firmato un sito esterno e viene accettato")


def test_old_ca_untouched():
    """CA gia' installata sui telefoni (senza vincoli): non si rifa'."""
    t = Path(tempfile.mkdtemp())
    certs.ensure(t)
    ca = t / certs.CA_FILE
    before = ca.read_bytes()
    certs.ensure(t)
    assert ca.read_bytes() == before


def test_leaf_skips_ips_outside_ca_constraints():
    """198.18/15 (VPN fake-ip) non e' tra le reti permesse dalla CA: nel certificato farebbe rifiutare la catena."""
    import ipaddress

    from cryptography.x509 import verification
    t = Path(tempfile.mkdtemp())
    orig = certs.lan_ips
    certs.lan_ips = lambda: ["192.168.1.5", "198.18.0.1", "192.0.0.2"]
    try:
        crt, _, ca = certs.ensure(t)
        certs.ensure(t)  # secondo giro: niente rigenerazione perenne per l'IP escluso
    finally:
        certs.lan_ips = orig
    leaf = x509.load_pem_x509_certificate(crt.read_bytes())
    sans = {str(i) for i in leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)}
    assert "192.168.1.5" in sans and "198.18.0.1" not in sans and "192.0.0.2" not in sans, sans
    b = verification.PolicyBuilder().store(verification.Store([x509.load_pem_x509_certificate(ca.read_bytes())]))
    b.build_server_verifier(x509.IPAddress(ipaddress.ip_address("192.168.1.5"))).verify(leaf, [])


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("ok")
