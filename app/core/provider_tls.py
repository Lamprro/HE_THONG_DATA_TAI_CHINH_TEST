"""Verified chain supplement for an issuer that omits its intermediate certificate."""
import ssl
from functools import lru_cache
from pathlib import Path
import certifi


@lru_cache(maxsize=1)
def eib_tls_context():
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=Path(__file__).parent / 'certs' / 'digicert-g5-tls-rsa4096-sha384-2021-ca1.pem')
    return context
