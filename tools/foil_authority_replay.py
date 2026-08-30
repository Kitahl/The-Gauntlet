"""One-use replay guard for host-consumed FOIL authority tokens."""

from __future__ import annotations

from dataclasses import dataclass, field

from foil_candidate_state import (
    AuthorityIssuer,
    AuthorityToken,
    CandidateBinding,
    CandidateState,
)


@dataclass
class AuthorityReplayGuard:
    """Consume a valid authority nonce once within one host process.

    Durable hosts should persist consumed nonces in their own transactional
    store.  This dependency-free guard provides the same fail-closed contract
    for a single process and never performs persistence itself.
    """

    _consumed: set[tuple[str, str]] = field(default_factory=set, init=False, repr=False)

    def consume(
        self,
        token: AuthorityToken,
        issuer: AuthorityIssuer,
        binding: CandidateBinding,
        *,
        now: str,
        expected_state: CandidateState,
    ) -> bool:
        if not isinstance(token, AuthorityToken):
            raise TypeError("token must be AuthorityToken")
        if not isinstance(issuer, AuthorityIssuer):
            raise TypeError("issuer must be AuthorityIssuer")
        if not isinstance(binding, CandidateBinding):
            raise TypeError("binding must be CandidateBinding")
        key = (token.issuer_id, token.nonce)
        if key in self._consumed:
            return False
        if not issuer.verify(
            token,
            binding,
            now=now,
            expected_state=expected_state,
        ):
            return False
        self._consumed.add(key)
        return True

    def consumed(self, token: AuthorityToken) -> bool:
        if not isinstance(token, AuthorityToken):
            raise TypeError("token must be AuthorityToken")
        return (token.issuer_id, token.nonce) in self._consumed
