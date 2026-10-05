"""Tests für die Versions-Odometer-Logik in bump_version.py: die 3. Stelle
wird pro Build erhöht, läuft bei 99 über und schiebt den Übertrag auf die
2. (und ggf. 1.) Stelle weiter - genau wie ein Kilometerzähler."""
import bump_version

try:
    import pytest
except ImportError:  # lokaler unittest-Lauf ohne pytest (CLAUDE.md) - Tests laufen in der CI
    pytest = None


if pytest is not None:

    @pytest.fixture(autouse=True)
    def _nie_die_echte_compose_datei(tmp_path, monkeypatch):
        # main() zieht seit H-2 auch den Image-Tag in compose.yaml nach - kein Test darf die
        # echte Datei im Repo verändern.
        monkeypatch.setattr(bump_version, "COMPOSE_DATEI", tmp_path / "compose.yaml")


def test_normaler_fall_erhoeht_nur_die_dritte_stelle():
    assert bump_version.naechste_version((1, 0, 0)) == (1, 0, 1)
    assert bump_version.naechste_version((1, 2, 41)) == (1, 2, 42)


def test_dritte_stelle_laeuft_bei_99_ueber_und_erhoeht_die_zweite():
    assert bump_version.naechste_version((1, 0, 99)) == (1, 1, 0)
    assert bump_version.naechste_version((2, 5, 99)) == (2, 6, 0)


def test_zweite_stelle_laeuft_bei_99_ueber_und_erhoeht_die_erste():
    assert bump_version.naechste_version((1, 99, 99)) == (2, 0, 0)


def test_version_lesen_ohne_datei_beginnt_bei_1_0_0(tmp_path, monkeypatch):
    monkeypatch.setattr(bump_version, "VERSION_DATEI", tmp_path / "version.txt")
    assert bump_version.version_lesen() == (1, 0, 0)


def test_main_schreibt_version_txt_und_version_info_txt(tmp_path, monkeypatch):
    version_datei = tmp_path / "version.txt"
    version_info_datei = tmp_path / "version_info.txt"
    version_py_datei = tmp_path / "version.py"
    version_datei.write_text("1.0.99\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    monkeypatch.setattr(bump_version, "VERSION_INFO_DATEI", version_info_datei)
    monkeypatch.setattr(bump_version, "VERSION_PY_DATEI", version_py_datei)
    # Nie das echte docs/HANDBUCH.md anfassen
    monkeypatch.setattr(bump_version, "HANDBUCH_DATEI", tmp_path / "HANDBUCH.md")

    ergebnis = bump_version.main()

    assert ergebnis == "1.1.0"
    assert version_datei.read_text(encoding="utf-8").strip() == "1.1.0"
    inhalt = version_info_datei.read_text(encoding="utf-8")
    assert 'filevers=(1, 1, 0, 0)' in inhalt
    assert 'StringStruct("FileVersion", "1.1.0.0")' in inhalt
    assert 'StringStruct("ProductVersion", "1.1.0.0")' in inhalt
    assert 'VERSION = "1.1.0"' in version_py_datei.read_text(encoding="utf-8")


def test_version_py_schreiben_enthaelt_versionskonstante(tmp_path, monkeypatch):
    version_py_datei = tmp_path / "version.py"
    monkeypatch.setattr(bump_version, "VERSION_PY_DATEI", version_py_datei)

    bump_version.version_py_schreiben("2.3.4")

    inhalt = version_py_datei.read_text(encoding="utf-8")
    assert 'VERSION = "2.3.4"' in inhalt
    # Muss als reguläres Python-Modul importierbar sein (so bindet app.py es ein).
    namensraum: dict = {}
    exec(compile(inhalt, str(version_py_datei), "exec"), namensraum)
    assert namensraum["VERSION"] == "2.3.4"


def test_version_lesen_mit_ungueltigem_inhalt_wirft_fehler(tmp_path, monkeypatch):
    version_datei = tmp_path / "version.txt"
    version_datei.write_text("nicht-gueltig\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    try:
        bump_version.version_lesen()
    except ValueError:
        pass
    else:
        raise AssertionError("erwartete ValueError bei ungültiger Versionsnummer")


def _handbuch_patchen(tmp_path, monkeypatch, inhalt: bytes):
    handbuch = tmp_path / "HANDBUCH.md"
    handbuch.write_bytes(inhalt)
    monkeypatch.setattr(bump_version, "HANDBUCH_DATEI", handbuch)
    return handbuch


def test_main_zieht_handbuch_version_nach_und_laesst_rest_unveraendert(tmp_path, monkeypatch):
    version_datei = tmp_path / "version.txt"
    version_datei.write_text("1.0.31\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    monkeypatch.setattr(bump_version, "VERSION_INFO_DATEI", tmp_path / "version_info.txt")
    monkeypatch.setattr(bump_version, "VERSION_PY_DATEI", tmp_path / "version.py")
    vorher = (
        "# Benutzerhandbuch\r\n\r\n"
        "Stand: Version 1.0.31. Alle Screenshots zeigen erfundene Testdaten.\r\n\r\n"
        "Später im Text: Stand: Version 1.0.5. bleibt stehen.\r\n"
    ).encode("utf-8")
    handbuch = _handbuch_patchen(tmp_path, monkeypatch, vorher)

    assert bump_version.main() == "1.0.32"

    # Nur die erste Versionszeile ändert sich, CRLF-Zeilenenden bleiben erhalten
    assert handbuch.read_bytes() == vorher.replace(
        b"Stand: Version 1.0.31.", b"Stand: Version 1.0.32.", 1)


def test_handbuch_version_schreiben_ohne_datei_ist_kein_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(bump_version, "HANDBUCH_DATEI", tmp_path / "fehlt" / "HANDBUCH.md")
    bump_version.handbuch_version_schreiben("1.2.3")
    assert not (tmp_path / "fehlt").exists()


def test_handbuch_version_schreiben_ohne_versionszeile_laesst_datei_unveraendert(tmp_path, monkeypatch):
    vorher = "# Handbuch\n\nKeine Versionsangabe hier.\n".encode("utf-8")
    handbuch = _handbuch_patchen(tmp_path, monkeypatch, vorher)
    bump_version.handbuch_version_schreiben("1.2.3")
    assert handbuch.read_bytes() == vorher


def test_main_zaehlt_nicht_hoch_wenn_handbuch_nicht_lesbar_ist(tmp_path, monkeypatch):
    # Handbuch-Pfad zeigt auf einen Ordner -> Öffnen scheitert (wie bei einer gesperrten Datei)
    version_datei = tmp_path / "version.txt"
    version_datei.write_text("1.0.31\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    monkeypatch.setattr(bump_version, "VERSION_INFO_DATEI", tmp_path / "version_info.txt")
    monkeypatch.setattr(bump_version, "VERSION_PY_DATEI", tmp_path / "version.py")
    ordner = tmp_path / "HANDBUCH.md"
    ordner.mkdir()
    monkeypatch.setattr(bump_version, "HANDBUCH_DATEI", ordner)

    try:
        bump_version.main()
    except OSError:
        pass
    else:
        raise AssertionError("erwartete OSError beim nicht lesbaren Handbuch")

    assert version_datei.read_text(encoding="utf-8") == "1.0.31\n"
    assert not (tmp_path / "version_info.txt").exists()
    assert not (tmp_path / "version.py").exists()


def test_main_zieht_compose_image_tag_nach_und_laesst_rest_unveraendert(tmp_path, monkeypatch):
    version_datei = tmp_path / "version.txt"
    version_datei.write_text("1.0.42\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    monkeypatch.setattr(bump_version, "VERSION_INFO_DATEI", tmp_path / "version_info.txt")
    monkeypatch.setattr(bump_version, "VERSION_PY_DATEI", tmp_path / "version.py")
    monkeypatch.setattr(bump_version, "HANDBUCH_DATEI", tmp_path / "HANDBUCH.md")
    vorher = (
        b"services:\r\n"
        b"  db:\r\n"
        b"    image: postgres:16.15@sha256:abc\r\n"
        b"  web:\r\n"
        b"    image: ${SHS_WEB_IMAGE:-ghcr.io/mbruver-source/shs-web:1.0.42}\r\n"
    )
    compose = tmp_path / "compose.yaml"
    compose.write_bytes(vorher)

    assert bump_version.main() == "1.0.43"

    assert compose.read_bytes() == vorher.replace(b"shs-web:1.0.42}", b"shs-web:1.0.43}")


def test_compose_version_schreiben_ohne_datei_oder_tag_ist_kein_fehler(tmp_path):
    bump_version.compose_version_schreiben("1.2.3")  # Datei fehlt (Fixture-Pfad)
    compose = tmp_path / "compose.yaml"
    vorher = b"services:\n  web:\n    image: ghcr.io/mbruver-source/shs-web:latest\n"
    compose.write_bytes(vorher)
    bump_version.compose_version_schreiben("1.2.3")
    assert compose.read_bytes() == vorher


def test_echte_compose_datei_enthaelt_den_versionierten_tag():
    # Fällt auf, falls jemand compose.yaml umbaut und bump_version den Tag nicht mehr findet.
    inhalt = (bump_version.HIER / "compose.yaml").read_text(encoding="utf-8")
    version = (bump_version.HIER / "version.txt").read_text(encoding="utf-8").strip()
    assert bump_version._COMPOSE_IMAGE_TAG.search(inhalt)
    assert f"/shs-web:{version}}}" in inhalt
