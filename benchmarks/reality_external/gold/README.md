# Gold directory

Readable gold MUST NOT be committed.

`gold.enc` is intentionally absent in this partial build because complete canonical gold has not been materialized. Creating ciphertext for only a subset would make the repository look complete when it is not.

After all legally usable gold is assembled locally, run `../tools/seal_gold.py` and commit `gold.enc` only if the script reports a successful decrypt-and-hash round trip. The generated key stays local-only.
