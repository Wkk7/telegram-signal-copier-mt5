import unittest

from copier.parser import Close, Signal, parse


class ParserTest(unittest.TestCase):
    def test_classic_format(self):
        s = parse("BUY EURUSD @ 1.0850  SL 1.0820  TP 1.0880 TP2 1.0910")
        self.assertEqual(s, Signal("buy", "EURUSD", "market", 1.0850, 1.0820, [1.0880, 1.0910]))

    def test_symbol_first_with_colons(self):
        s = parse("XAUUSD SELL NOW 2350\nSL: 2360\nTP1: 2340\nTP2: 2330")
        self.assertEqual((s.side, s.symbol, s.entry, s.sl, s.tps), ("sell", "XAUUSD", 2350, 2360, [2340, 2330]))

    def test_alias_limit_and_range(self):
        s = parse("Gold buy limit 2330-2328, stop loss 2320, take profit 2345")
        self.assertEqual((s.symbol, s.order_type, s.entry, s.sl, s.tps), ("XAUUSD", "limit", 2330, 2320, [2345]))

    def test_slash_pair_and_decimal_comma(self):
        s = parse("EUR/USD long entry 1,0850 sl 1,0820 tp 1,0900")
        self.assertEqual((s.symbol, s.side, s.entry, s.sl, s.tps), ("EURUSD", "buy", 1.085, 1.082, [1.09]))

    def test_emojis_and_noise(self):
        s = parse("🔥 GBPJPY SELL 🔥\nEntry: 191.20\n❌ SL 191.80\n✅ TP 190.50\n✅ TP 190.00")
        self.assertEqual((s.symbol, s.side, s.entry, s.sl, s.tps), ("GBPJPY", "sell", 191.20, 191.80, [190.5, 190.0]))

    def test_market_without_price(self):
        s = parse("US30 buy now sl 38900 tp 39400")
        self.assertEqual((s.symbol, s.entry, s.sl, s.tps), ("US30", None, 38900, [39400]))

    def test_close_instruction(self):
        self.assertEqual(parse("Close GBPUSD now, take profits"), Close("GBPUSD"))

    def test_no_stop_loss_is_rejected(self):
        self.assertIsNone(parse("BUY EURUSD 1.0850 TP 1.0900"))

    def test_wrong_side_stop_is_rejected(self):
        self.assertIsNone(parse("BUY EURUSD 1.0850 SL 1.0900 TP 1.0950"))

    def test_chat_messages_are_ignored(self):
        for text in ("TP1 hit +30 pips 🎉", "Good morning traders", "EURUSD looks bullish today"):
            self.assertIsNone(parse(text), text)


if __name__ == "__main__":
    unittest.main()
