"""`robot-litearm` 参数解析测试（不需要 Forge/SDK 运行时）。"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import litearm_robot.main as cli


def _capture(monkeypatch, name):
    seen = {}

    def fake(config_path, *, fake=False, debug=False, **kwargs):
        seen.update(config=config_path, fake=fake, debug=debug, **kwargs)
        return 0

    monkeypatch.setattr(cli, name, fake)
    return seen


def test_top_level_config_reaches_subcommand(monkeypatch):
    seen = _capture(monkeypatch, "_probe")
    assert cli.main(["--config", "top.yaml", "probe"]) == 0
    assert seen["config"] == "top.yaml"


def test_subcommand_config_still_wins(monkeypatch):
    seen = _capture(monkeypatch, "_probe")
    assert cli.main(["probe", "--config", "sub.yaml"]) == 0
    assert seen["config"] == "sub.yaml"


def test_top_level_config_reaches_default_run(monkeypatch):
    seen = _capture(monkeypatch, "_run_node")
    assert cli.main(["--config", "top.yaml"]) == 0
    assert seen["config"] == "top.yaml"


def test_all_subcommands_accept_debug(monkeypatch):
    probe = _capture(monkeypatch, "_probe")
    home = _capture(monkeypatch, "_home")
    run = _capture(monkeypatch, "_run_node")

    assert cli.main(["probe", "--debug", "--fake"]) == 0
    assert cli.main(["home", "--debug", "--fake"]) == 0
    assert cli.main(["run", "--debug", "--fake"]) == 0
    assert cli.main(["--debug", "run", "--fake"]) == 0

    assert probe["debug"] is False  # probe/home 不使用节点 debug 参数
    assert home["debug"] is False
    assert run["debug"] is True


def test_run_honours_config_debug(monkeypatch, tmp_path):
    config = tmp_path / "robot.yaml"
    config.write_text("debug: true\n", encoding="utf-8")

    captured = {}

    def fake_run_node(driver, *, debug=False):
        captured["debug"] = debug
        return 0

    class FakeDriver:
        def __init__(self):
            self.config = SimpleNamespace(debug=True)

        def connect(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(cli, "_make_driver", lambda path, fake=False: FakeDriver())
    monkeypatch.setattr("litearm_robot.node.run_node", fake_run_node)

    assert cli.main(["--config", str(config), "run"]) == 0
    assert captured["debug"] is True
    assert logging.getLogger().level == logging.DEBUG
