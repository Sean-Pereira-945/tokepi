import pytest

jwt = pytest.importorskip("jwt")

from driftguard.server.security import (
    api_key_hint,
    create_session_token,
    decode_session_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip_and_salting():
    first, second = hash_password("s3cret-pass"), hash_password("s3cret-pass")
    assert first != second
    assert first.startswith("scrypt$")
    assert verify_password("s3cret-pass", first)
    assert not verify_password("wrong", first)


@pytest.mark.parametrize("stored", [None, "", "md5$abc", "scrypt$broken"])
def test_verify_password_rejects_missing_or_malformed_hashes(stored):
    assert verify_password("anything", stored) is False


def test_api_keys_are_prefixed_unique_and_hashed():
    key = generate_api_key()
    assert key.startswith("dg_live_") and len(key) > 40
    assert key != generate_api_key()
    assert len(hash_api_key(key)) == 64 and hash_api_key(key) == hash_api_key(key)
    assert api_key_hint(key) == key[:12]


def test_session_tokens_verify_and_expire():
    token, jti, _ = create_session_token("acct-1", "secret" * 8, ttl_hours=1)
    assert decode_session_token(token, "secret" * 8) == ("acct-1", jti)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_session_token(token, "other" * 8)
    expired, _, _ = create_session_token("acct-1", "secret" * 8, ttl_hours=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_session_token(expired, "secret" * 8)
