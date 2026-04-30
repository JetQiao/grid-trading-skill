"""Unit tests for data/symbol.py — symbol parsing and per-source codes."""

from __future__ import annotations

import unittest

from grid_trading.data.symbol import detect_market, normalize_symbol


class TestDetectMarket(unittest.TestCase):

    def test_a_share_six_digit(self):
        self.assertEqual(detect_market("600519"), "a-share")
        self.assertEqual(detect_market("000001"), "a-share")

    def test_a_share_with_prefix(self):
        self.assertEqual(detect_market("sh600519"), "a-share")
        self.assertEqual(detect_market("sz000001"), "a-share")

    def test_a_share_with_suffix(self):
        self.assertEqual(detect_market("600519.SS"), "a-share")
        self.assertEqual(detect_market("000001.SZ"), "a-share")

    def test_hk(self):
        self.assertEqual(detect_market("00700"), "hk")
        self.assertEqual(detect_market("0700.HK"), "hk")
        self.assertEqual(detect_market("hk00700"), "hk")

    def test_us(self):
        self.assertEqual(detect_market("AAPL"), "us")
        self.assertEqual(detect_market("aapl"), "us")
        self.assertEqual(detect_market("TSLA"), "us")

    def test_crypto_slash(self):
        self.assertEqual(detect_market("BTC/USDT"), "crypto")
        self.assertEqual(detect_market("ETH/USD"), "crypto")

    def test_crypto_dash(self):
        self.assertEqual(detect_market("BTC-USDT"), "crypto")

    def test_crypto_concatenated(self):
        self.assertEqual(detect_market("BTCUSDT"), "crypto")
        self.assertEqual(detect_market("ETHUSDC"), "crypto")

    def test_unknown(self):
        self.assertEqual(detect_market(""), "unknown")
        self.assertEqual(detect_market("???"), "unknown")


class TestSourceCodes(unittest.TestCase):

    def test_eastmoney_secid_a_share(self):
        sym = normalize_symbol("600519")
        self.assertEqual(sym.eastmoney_secid, "1.600519")
        sym = normalize_symbol("000001")
        self.assertEqual(sym.eastmoney_secid, "0.000001")

    def test_eastmoney_secid_hk(self):
        sym = normalize_symbol("00700")
        self.assertEqual(sym.eastmoney_secid, "116.00700")

    def test_eastmoney_secid_us(self):
        sym = normalize_symbol("AAPL")
        self.assertEqual(sym.eastmoney_secid, "105.AAPL")

    def test_yahoo_code(self):
        self.assertEqual(normalize_symbol("600519").yahoo_code, "600519.SS")
        self.assertEqual(normalize_symbol("000001").yahoo_code, "000001.SZ")
        self.assertEqual(normalize_symbol("00700").yahoo_code, "0700.HK")
        self.assertEqual(normalize_symbol("AAPL").yahoo_code, "AAPL")

    def test_sina_code(self):
        self.assertEqual(normalize_symbol("600519").sina_code, "sh600519")
        self.assertEqual(normalize_symbol("000001").sina_code, "sz000001")
        self.assertEqual(normalize_symbol("AAPL").sina_code, "gb_aapl")

    def test_crypto_base_quote(self):
        sym = normalize_symbol("BTC/USDT")
        self.assertEqual(sym.base, "BTC")
        self.assertEqual(sym.quote, "USDT")
        self.assertEqual(sym.code, "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
