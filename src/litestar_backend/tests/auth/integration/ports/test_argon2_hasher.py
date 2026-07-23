from auth.ports.driven import Argon2Hasher


class TestArgon2Hasher:
    def test_hash_verify_roundtrip(self) -> None:
        """Given a password, When hashed then verified, Then True."""
        hasher = Argon2Hasher()
        assert hasher.verify("s3cret-pass", hasher.hash("s3cret-pass"))

    def test_wrong_password_fails(self) -> None:
        """Given a hash, When verifying another password, Then False."""
        hasher = Argon2Hasher()
        assert not hasher.verify("other-pass", hasher.hash("s3cret-pass"))

    def test_malformed_hash_is_false_not_raise(self) -> None:
        """Given garbage instead of a hash, When verifying, Then False."""
        hasher = Argon2Hasher()
        assert not hasher.verify("s3cret-pass", "not-a-real-hash")

    def test_dummy_hash_is_stable_and_never_matches(self) -> None:
        """Given the dummy hash, When verifying real input, Then False -- and
        the dummy is computed once (same object per instance)."""
        hasher = Argon2Hasher()
        assert hasher.dummy_hash() is hasher.dummy_hash()
        assert not hasher.verify("s3cret-pass", hasher.dummy_hash())

    def test_hashes_are_salted(self) -> None:
        """Given the same password twice, When hashed, Then hashes differ."""
        hasher = Argon2Hasher()
        assert hasher.hash("s3cret-pass") != hasher.hash("s3cret-pass")
