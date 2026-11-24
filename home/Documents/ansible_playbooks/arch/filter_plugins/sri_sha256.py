"""Turn an nvfetcher SRI sha256 into the hex form ansible get_url expects."""

import base64


def sri_sha256_hex(value):
    algorithm, encoded = value.split("-", 1)
    if algorithm != "sha256":
        raise ValueError(f"expected sha256 SRI, got {algorithm}")
    return base64.b64decode(encoded).hex()


class FilterModule:
    def filters(self):
        return {"sri_sha256_hex": sri_sha256_hex}
