"""Tests for audience_server.py — AudienceServer voting and initialization."""

from unittest.mock import MagicMock

import pytest

from audience_server import AudienceServer


class TestServerInit:
    def test_server_init(self):
        sm = MagicMock()
        server = AudienceServer(port=9000, state_manager=sm)
        assert server.port == 9000
        assert server.state_manager is sm
        assert server.host == "0.0.0.0"

    def test_server_default_init(self):
        server = AudienceServer()
        assert server.port == 8767
        assert server.state_manager is None

    def test_client_count_initially_zero(self):
        server = AudienceServer()
        assert server.client_count == 0


class TestVoting:
    def test_consume_votes_empty(self):
        server = AudienceServer()
        result = server.consume_votes()
        assert result is None

    def test_consume_votes_returns_winner(self):
        server = AudienceServer()
        # Simulate votes: block 5 gets 3 votes, block 2 gets 1 vote
        server._block_votes[5].add("client_a")
        server._block_votes[5].add("client_b")
        server._block_votes[5].add("client_c")
        server._block_votes[2].add("client_d")
        server._client_votes["client_a"] = 5
        server._client_votes["client_b"] = 5
        server._client_votes["client_c"] = 5
        server._client_votes["client_d"] = 2

        result = server.consume_votes()
        assert result is not None
        assert result["block_id"] == 5
        assert result["voter_count"] == 3
        assert len(result["voter_ids"]) == 3
        assert result["round"] == 0

    def test_consume_votes_resets(self):
        server = AudienceServer()
        server._block_votes[1].add("c1")
        server._client_votes["c1"] = 1
        server.consume_votes()
        # After consuming, votes should be cleared
        assert server.consume_votes() is None

    def test_get_winning_block_id(self):
        server = AudienceServer()
        server._block_votes[10].add("c1")
        server._block_votes[10].add("c2")
        server._block_votes[20].add("c3")
        assert server.get_winning_block_id() == 10

    def test_get_winning_block_id_none(self):
        server = AudienceServer()
        assert server.get_winning_block_id() is None

    def test_get_vote_results(self):
        server = AudienceServer()
        server._block_votes[1].add("c1")
        server._block_votes[1].add("c2")
        server._block_votes[3].add("c3")
        results = server.get_vote_results()
        assert results == {1: 2, 3: 1}

    def test_vote_round_increments(self):
        server = AudienceServer()
        assert server._vote_round == 0
        server._block_votes[1].add("c1")
        server._client_votes["c1"] = 1
        server.consume_votes()
        assert server._vote_round == 1
        server._block_votes[2].add("c2")
        server._client_votes["c2"] = 2
        server.consume_votes()
        assert server._vote_round == 2


class TestTilt:
    def test_get_average_tilt_empty(self):
        server = AudienceServer()
        pitch, roll = server.get_average_tilt()
        assert pitch == 0.0
        assert roll == 0.0

    def test_get_average_tilt_single(self):
        server = AudienceServer()
        server._tilts["c1"] = (22.5, -22.5)
        pitch, roll = server.get_average_tilt()
        assert abs(pitch - 0.5) < 0.01
        assert abs(roll - (-0.5)) < 0.01

    def test_get_average_tilt_clamped(self):
        server = AudienceServer()
        server._tilts["c1"] = (90.0, -90.0)
        pitch, roll = server.get_average_tilt()
        assert pitch == 1.0
        assert roll == -1.0
