import unittest


IDENTITY = "gog:game"
HASH = "a" * 64
TOKEN = "capability-token"


def descriptor(**overrides):
    value = {
        "protocol": "TrainerRelay Cooperative Control v1",
        "schemaVersion": 1,
        "identity": IDENTITY,
        "trainerSha256": HASH,
        "session": {"pid": 10, "startTime": 20},
        "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
        "capabilityToken": TOKEN,
        "revision": 4,
        "operations": ["enable", "disable", "toggle"],
        "cheats": [
            {
                "id": "health",
                "label": "Infinite health",
                "operations": ["enable", "disable", "toggle"],
                "state": "disabled",
            }
        ],
    }
    value.update(overrides)
    return value


def ack(**overrides):
    value = {
        "protocol": "TrainerRelay Cooperative Control v1",
        "schemaVersion": 1,
        "identity": IDENTITY,
        "trainerSha256": HASH,
        "session": {"pid": 10, "startTime": 20},
        "capabilityToken": TOKEN,
        "commandId": "11111111-1111-4111-8111-111111111111",
        "cheatId": "health",
        "operation": "toggle",
        "accepted": True,
        "state": "enabled",
        "revision": 5,
        "freshUntil": 12.0,
    }
    value.update(overrides)
    return value


class CooperativeProtocolTests(unittest.TestCase):
    def test_descriptor_requires_v1_schema_identity_build_session_token_and_valid_endpoint(self):
        from trainer_relay.cooperative import decode_cooperative_descriptor

        decoded = decode_cooperative_descriptor(
            descriptor(), expected_identity=IDENTITY, expected_trainer_sha256=HASH, expected_session={"pid": 10, "startTime": 20}
        )
        self.assertEqual(decoded.identity, IDENTITY)
        self.assertEqual(decoded.trainer_sha256, HASH)
        self.assertEqual(decoded.revision, 4)
        self.assertEqual(decoded.cheats[0].state, "disabled")
        self.assertNotEqual(decoded.capability_token, "")

        for invalid in (
            {**descriptor(), "schemaVersion": 2},
            {**descriptor(), "protocol": "other"},
            {**descriptor(), "identity": "epic:other"},
            {**descriptor(), "trainerSha256": "b" * 64},
            {**descriptor(), "capabilityToken": ""},
            {**descriptor(), "endpoint": {"transport": "tcp", "address": "127.0.0.1"}},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "cooperative_"):
                    decode_cooperative_descriptor(invalid, expected_identity=IDENTITY, expected_trainer_sha256=HASH)

    def test_descriptor_rejects_unsupported_operations_and_non_monotonic_revisions(self):
        from trainer_relay.cooperative import decode_cooperative_descriptor

        for value in (
            {**descriptor(), "operations": ["shell"]},
            {**descriptor(), "revision": -1},
            {**descriptor(), "cheats": [{**descriptor()["cheats"][0], "state": "stale"}]},
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode_cooperative_descriptor(value, expected_identity=IDENTITY, expected_trainer_sha256=HASH)

    def test_ack_binds_command_identity_token_and_revision_and_requires_fresh_deadline(self):
        from trainer_relay.cooperative import decode_cooperative_ack, decode_cooperative_descriptor

        protocol_descriptor = decode_cooperative_descriptor(descriptor())
        decoded = decode_cooperative_ack(
            ack(), descriptor=protocol_descriptor, expected_command_id="11111111-1111-4111-8111-111111111111", now=10.0
        )
        self.assertTrue(decoded.accepted)
        self.assertEqual(decoded.state, "enabled")
        self.assertEqual(decoded.revision, 5)

        invalid_values = (
            {**ack(), "commandId": "22222222-2222-4222-8222-222222222222"},
            {**ack(), "capabilityToken": "wrong"},
            {**ack(), "revision": 3},
            {**ack(), "state": "enabled", "accepted": False},
            {**ack(), "operation": "shell"},
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode_cooperative_ack(
                        value,
                        descriptor=protocol_descriptor,
                        expected_command_id="11111111-1111-4111-8111-111111111111",
                        now=10.0,
                    )

    def test_stale_ack_is_unknown_and_boundary_does_not_authorize_missing_transport(self):
        from trainer_relay.cooperative import decode_cooperative_ack, decode_cooperative_descriptor

        protocol_descriptor = decode_cooperative_descriptor(descriptor())
        stale = decode_cooperative_ack(
            {**ack(), "freshUntil": 10.0},
            descriptor=protocol_descriptor,
            expected_command_id="11111111-1111-4111-8111-111111111111",
            now=10.1,
        )
        self.assertFalse(stale.fresh)
        self.assertEqual(stale.state, "unknown")

        from trainer_relay.cooperative import CooperativeControlBoundary

        boundary = CooperativeControlBoundary()
        self.assertIsNone(boundary.client_for(None))

    def test_descriptor_and_ack_reject_unbounded_revision_and_freshness(self):
        from trainer_relay.cooperative import decode_cooperative_ack, decode_cooperative_descriptor

        with self.assertRaisesRegex(ValueError, "cooperative_revision_invalid"):
            decode_cooperative_descriptor({**descriptor(), "revision": 2**63})

        protocol_descriptor = decode_cooperative_descriptor(descriptor())
        with self.assertRaisesRegex(ValueError, "cooperative_freshness_invalid"):
            decode_cooperative_ack(
                {**ack(), "freshUntil": 10**1000},
                descriptor=protocol_descriptor,
                expected_command_id="11111111-1111-4111-8111-111111111111",
                now=10.0,
            )

    def test_boundary_revalidates_dataclass_descriptors_before_returning_a_client(self):
        from trainer_relay.cooperative import CooperativeControlBoundary, CooperativeDescriptor

        forged = CooperativeDescriptor(
            IDENTITY,
            HASH,
            {"pid": 10, "startTime": 20},
            {"transport": "tcp", "address": "127.0.0.1"},
            TOKEN,
            1,
            ("toggle",),
            (),
        )
        self.assertIsNone(CooperativeControlBoundary(lambda _payload: None).client_for(forged))

    def test_client_rejects_an_operation_not_supported_by_the_selected_cheat(self):
        from trainer_relay.cooperative import CooperativeControlClient, decode_cooperative_descriptor

        protocol_descriptor = decode_cooperative_descriptor(
            descriptor(
                operations=["enable", "toggle"],
                cheats=[{"id": "health", "label": "Infinite health", "operations": ["enable"], "state": "disabled"}],
            )
        )
        calls = []

        def request(payload):
            calls.append(payload)
            return None

        client = CooperativeControlClient(protocol_descriptor, request)
        with self.assertRaisesRegex(ValueError, "cooperative_operation_invalid"):
            client.send("11111111-1111-4111-8111-111111111111", "health", "toggle")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
