"""Die Beschreibung eines Bedienelements traegt Kennwortfeld und Auswahlzustand.

Das Element ist nachgebaut; es wird kein Fenster gelesen.
"""

import importlib.util
from pathlib import Path

import pytest

PFAD = Path(__file__).resolve().parents[1] / "moire_agents" / "agents" / "handoff" / "screen_description.py"


def _modul():
    spec = importlib.util.spec_from_file_location("screen_description_test", PFAD)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class _Auswahl:
    def __init__(self, gewaehlt):
        self.IsSelected = gewaehlt


class _Element:
    Name = ""
    ControlTypeName = "EditControl"
    ClassName = ""
    AutomationId = ""
    IsEnabled = True
    IsKeyboardFocusable = True

    def __init__(self, kennwort=False, auswahl=None):
        self.IsPassword = kennwort
        self._auswahl = auswahl

    def GetSelectionItemPattern(self):
        return self._auswahl


class _OhneKennwort(_Element):
    @property
    def IsPassword(self):
        raise RuntimeError("nicht unterstuetzt")

    @IsPassword.setter
    def IsPassword(self, _):
        pass


@pytest.mark.parametrize(("element", "kennwort", "gewaehlt"), [
    (_Element(kennwort=True), True, None),
    (_Element(kennwort=False, auswahl=_Auswahl(True)), False, True),
    (_Element(auswahl=_Auswahl(False)), False, False),
    (_OhneKennwort(), None, None),
])
def test_kennwortfeld_und_auswahlzustand(element, kennwort, gewaehlt):
    info = _modul()._uia_describe_control(element)
    assert info["is_password"] is kennwort
    assert info.get("is_selected") is gewaehlt
    assert ("SelectionItem" in info["supported_actions"]) is (gewaehlt is not None)
