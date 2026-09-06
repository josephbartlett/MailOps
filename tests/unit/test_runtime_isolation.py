import os
import socket

import pytest


def test_tests_have_no_inherited_mailops_credentials(tmp_path):
    assert {name for name in os.environ if name.startswith("MAILOPS_")} == {"MAILOPS_HOME"}
    assert os.environ["MAILOPS_HOME"] == str(tmp_path / ".mailops")
    with socket.socket() as client, pytest.raises(OSError, match="live connections are disabled"):
        client.connect(("127.0.0.1", 1143))
