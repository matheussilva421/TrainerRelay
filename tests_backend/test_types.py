import unittest

from trainer_relay.types import DiscoveryState, RelayStatus


class RelayTypeTests(unittest.TestCase):
    def test_rejects_unknown_runtime_states(self):
        with self.assertRaises(ValueError):
            DiscoveryState("guessed")
        with self.assertRaises(ValueError):
            RelayStatus("guessed")

    def test_string_enums_preserve_rpc_wire_values(self):
        self.assertEqual(str(DiscoveryState.SESSION), "session")
        self.assertEqual(str(RelayStatus.WAITING_FOR_GAME), "waiting_for_game")


if __name__ == "__main__":
    unittest.main()
