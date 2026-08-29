# Commitments

`inputs.sha256` commits the exact blind input artifacts currently materialized in Git. In this partial fail-closed build it contains the two LiveIdeaBench v2 input hashes only.

Gold commitment files remain intentionally absent because the complete canonical gold package is not yet materialized. Never write placeholder SHA-256 values. `gold_plaintext.sha256` and `gold_ciphertext.sha256` become valid only when computed from the exact complete gold artifacts they commit to and encryption has passed the required decrypt-and-hash round trip.
