"""Tests für die Versions-Odometer-Logik in bump_version.py: die 3. Stelle
wird pro Build erhöht, läuft bei 99 über und schiebt den Übertrag auf die
2. (und ggf. 1.) Stelle weiter - genau wie ein Kilometerzähler."""
import bump_version


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
    version_datei.write_text("1.0.99\n", encoding="utf-8")
    monkeypatch.setattr(bump_version, "VERSION_DATEI", version_datei)
    monkeypatch.setattr(bump_version, "VERSION_INFO_DATEI", version_info_datei)

    ergebnis = bump_version.main()

    assert ergebnis == "1.1.0"
    assert version_datei.read_text(encoding="utf-8").strip() == "1.1.0"
    inhalt = version_info_datei.read_text(encoding="utf-8")
    assert 'filevers=(1, 1, 0, 0)' in inhalt
    assert 'StringStruct("FileVersion", "1.1.0.0")' in inhalt
    assert 'StringStruct("ProductVersion", "1.1.0.0")' in inhalt


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
