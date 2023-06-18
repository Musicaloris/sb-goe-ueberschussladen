"""Custom-Funktionen für das SB-GoE-Überschussladen
CC-BY Musicaloris
"""


def konfigurationswerte_pruefen(konf: dict):
    """Prüf, ob die Werte aus der config.toml gültige Werte haben.

    :param konf: Objekt aus dem TOML-Import
    :return: Prüfung erfolgreich, oder nicht?
    """
    if konf['laden_prio'] not in konf['laden_prio_text']:
        raise ValueError('Fehler: Lademodus in laden_prio hat ungültigen Wert!')
    if not isinstance(konf['ladeleistung_puffer_W'], (int, float)):
        raise TypeError('Fehler:  ladeleistung_puffer_W hat ungültigen Wert!')
    if konf['ladeleistung_puffer_W'] < 0:
        raise ValueError('Fehler:  ladeleistung_puffer_W hat ungültigen Wert!')
    if not isinstance(konf['wartezeit'], (int, float)):
        raise TypeError('Fehler:  wartezeit hat ungültigen Wert!')
    if konf['wartezeit'] < 0:
        raise ValueError('Fehler:  wartezeit hat ungültigen Wert!')
    if not isinstance(konf['min_batterie_soc'], (int, float)):
        raise TypeError('Fehler:  min_batterie_soc hat ungültigen Wert!')
    if not isinstance(konf['min_batterie_soc'], int) or not 0 <= konf['min_batterie_soc'] <= 100:
        raise ValueError('Fehler:  min_batterie_soc hat ungültigen Wert!')
    if not isinstance(konf['sb_max_w'], (int, float)):
        raise TypeError('Fehler:  sb_max_w hat ungültigen Wert!')
    if konf['sb_max_w'] < 0:
        raise ValueError('Fehler:  sb_max_w hat ungültigen Wert!')
    if not isinstance(konf['logging_nrg'], bool):
        raise TypeError('Fehler:  logging_nrg hat ungültigen Wert!')
    if not isinstance(konf['logging_events'], bool):
        raise TypeError('Fehler:  logging_events hat ungültigen Wert!')
    if not isinstance(konf['simulieren'], bool):
        raise TypeError('Fehler:  simulieren hat ungültigen Wert!')
    if not isinstance(konf['zoe_modus'], bool):
        raise TypeError('Fehler:  zoe_modus hat ungültigen Wert!')

    return True
