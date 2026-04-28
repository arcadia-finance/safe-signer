from src.utils.signatures import concatenate, sort_by_signer

SAMPLE_SIGNERS = {
    "0x3A1b2C3d4E5f6A7B8c9D0E1F2a3B4c5D6e7F8a9B": "sig_1",
    "0x7e8F9a0B1c2D3e4F5A6b7C8d9E0f1A2B3c4D5e6F": "sig_2",
    "0xBb1C2d3E4f5A6b7C8D9e0F1a2B3c4D5E6f7A8b9C": "sig_3",
    "0xCa2D3e4F5a6B7c8D9E0f1A2b3C4d5E6F7a8B9c0D": "sig_4",
    "0xDb3E4f5A6b7C8d9E0F1a2B3c4D5e6F7A8b9C0d1E": "sig_5",
    "0xFc4F5a6B7c8D9e0F1A2b3C4d5E6f7A8B9c0D1e2F": "sig_6",
}


class TestSortBySignerProducesAscendingOrder:
    def test_sample_signers_ascending(self):
        result = sort_by_signer(SAMPLE_SIGNERS)
        values = [int(addr, 16) for addr, _ in result]
        assert values == sorted(values)

    def test_all_pairs_numerically_ordered(self):
        result = sort_by_signer(SAMPLE_SIGNERS)
        addrs = [int(addr, 16) for addr, _ in result]
        for i in range(len(addrs) - 1):
            assert addrs[i] < addrs[i + 1]


class TestSortBySignerHandlesMixedCase:
    def test_lowercase_start_sorted_correctly(self):
        sigs = {
            "0xaB5801a7D398351b8bE11C439e05C5B3259aeC9B": "sig_low",
            "0xF192e3A4b5C6d7E8f9A0B1c2D3e4F5a6B7c8D9e0": "sig_high",
        }
        result = sort_by_signer(sigs)
        addrs = [int(addr, 16) for addr, _ in result]
        assert addrs == sorted(addrs)
        assert result[0][0].startswith("0xaB")

    def test_uppercase_F_vs_lowercase_a(self):
        sigs = {
            "0xF000000000000000000000000000000000000000": "sig_f",
            "0xa000000000000000000000000000000000000000": "sig_a",
        }
        result = sort_by_signer(sigs)
        assert result[0][0].startswith("0xa")
        assert result[1][0].startswith("0xF")

    def test_case_insensitive_sort(self):
        addr_lower = "0xabcdef0000000000000000000000000000000000"
        addr_upper = "0xABCDEF0000000000000000000000000000000000"
        assert int(addr_lower, 16) == int(addr_upper, 16)

    def test_three_signers_with_problematic_ordering(self):
        sigs = {
            "0xaB5801a7D398351b8bE11C439e05C5B3259aeC9B": "sig_1",
            "0xB12345678901234567890123456789012345abcd": "sig_2",
            "0xF192e3A4b5C6d7E8f9A0B1c2D3e4F5a6B7c8D9e0": "sig_3",
        }
        result = sort_by_signer(sigs)
        addrs = [int(addr, 16) for addr, _ in result]
        assert addrs == sorted(addrs)


class TestSortBySignerPreservesPairing:
    def test_signatures_stay_paired_with_addresses(self):
        addr_high = "0xF192e3A4b5C6d7E8f9A0B1c2D3e4F5a6B7c8D9e0"
        addr_low = "0x3A1b2C3d4E5f6A7B8c9D0E1F2a3B4c5D6e7F8a9B"
        sigs = {
            addr_high: "aabbcc",
            addr_low: "ddeeff",
        }
        result = sort_by_signer(sigs)
        assert result[0] == (addr_low, "ddeeff")
        assert result[1] == (addr_high, "aabbcc")

    def test_empty_dict(self):
        assert sort_by_signer({}) == []

    def test_single_signer(self):
        sigs = {"0xABCD000000000000000000000000000000000000": "only_sig"}
        result = sort_by_signer(sigs)
        assert len(result) == 1
        assert result[0][1] == "only_sig"


class TestConcatenate:
    def test_concatenates_in_order(self):
        items = [
            ("0xaaa", "1111"),
            ("0xbbb", "2222"),
            ("0xccc", "3333"),
        ]
        assert concatenate(items) == "0x111122223333"

    def test_empty_list(self):
        assert concatenate([]) == "0x"

    def test_single_signature(self):
        items = [("0xaaa", "abcdef")]
        assert concatenate(items) == "0xabcdef"
