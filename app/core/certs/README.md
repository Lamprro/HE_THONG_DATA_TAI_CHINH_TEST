# EIB certificate chain

On 2026-10-24, media.eximbank.com.vn omitted its intermediate certificate.
The supplement is a public DigiCert CA certificate, not a private key.

Source: https://cacerts.digicert.com/DigiCertG5TLSRSA4096SHA3842021CA1-1.crt

SHA-256: c6270a150691fbe190d831f5139bdfeecf7b298b4fa0ca17306a69d7e91e7ba2

The EIB leaf plus this intermediate passed OpenSSL verification against certifi's
normal CA bundle. The intermediate expires on 2031-04-13. Only the EIB proxy uses
the supplemented context; hostname and certificate verification remain enabled.
Recheck the upstream chain on certificate rotation and remove the supplement
when the issuer serves its complete chain.
