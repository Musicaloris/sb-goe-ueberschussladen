"""Custom-Funktionen für das SB-GoE-Überschussladen
CC-BY Musicaloris
"""


def konfigurationswerte_pruefen(konf: dict):
    """Prüft, ob die Werte aus der config.toml gültige Werte haben.

    :param konf: Objekt aus dem TOML-Import
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


def daten_holen(objekt_name: str, objekt: dict, url: str, konf: dict):
    """Holt sich die JSON-Daten von der Hardware über das lokale Netzwerk.

    :param objekt_name: Entweder "Go-E" oder "SB"
    :param objekt: dict-Objekt aus den JSON-Daten und Metainformationen, min. 'zeitstempel' muss initialisiert sein
    :param url: URL, von der die Funktion per GET die JSON-Daten holt. Wird im Programmkopf definiert.
    :param konf: dict-Objekt mit der aktuellen Konfiguration
    :return: dict-Objekt aus den aktualisierten JSON-Daten falls erfolgreich, False falls nicht erfolgreich
    """
    import time
    import requests

    if time.time() >= objekt['zeitstempel'] + konf['wartezeit']:
        try:
            print(f'    Hole aktuelle Daten von {objekt_name}...', end='', flush=True)
            antwort = requests.get(url, timeout=konf['wartezeit'])
        except Exception as connect_err:
            log_event(f'{objekt_name} Verbindungsfehler, Details: {connect_err}', konf)
        else:
            if antwort.status_code == 200:
                print('OK')
                return {'objekt': objekt_name, 'status_code': antwort.status_code,
                        'zeitstempel': time.time()} | antwort.json()
            else:
                log_event(f'{objekt_name} HTTP Fehler Status {antwort.status_code}', konf)
                return {'objekt': objekt_name, 'zeitstempel': time.time()}
    else:
        return objekt


def goe_ladeleistung_bestimmen(sb_status_i: dict, goe_status_i: dict, ladekurve: dict, konf: dict):
    """Errechnet die aktuell maximal mögliche Ladeleistung anhand der gegebenen Bedingungen und der Ladekurve.

    :param sb_status_i: dict-Objekt aus den JSON-Daten und Metainformationen der SonnenBatterie
    :param goe_status_i: dict-Objekt aus den JSON-Daten und Metainformationen des Go-eChargers
    :param ladekurve: dict-Objekt mit der aktuellen Ladekurve
    :param konf: dict-Objekt mit der aktuellen Konfiguration
    :return: dict-Objekt mit der errechneten Leistung in A und W
    """
    import math

    goe_leistung_w = goe_status_i['nrg'][11] * 10  # Go-E gibt die Leistung in Vielfachen von 10W aus
    lade_soll_w = 0  # Initialisieren
    goe_u = math.fsum(goe_status_i['nrg'][0:3]) / 3  # Durchschnitt über die Spannungen der drei Einzelphasen

    print(f'Ladeleistung wird bestimmt im Modus {konf["laden_prio"]}: {konf["laden_prio_text"][konf["laden_prio"]]}.\n')

    if konf['laden_prio'] == 'Überschuss':  # Getestet
        battery_status = sb_status_i['BatteryCharging'], sb_status_i['BatteryDischarging']
        if battery_status == (True, False):  # SonnenBatterie lädt, SB-Ladestrom muss beschützt werden
            lade_soll_w = (sb_status_i["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           + sb_status_i['Pac_total_W']  # Ladeleistung SB, negativ beim Aufladen, daher +
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
        elif battery_status == (False, True):  # SonnenBatterie entlädt, in diesem Modus nicht erwünscht!
            lade_soll_w = (sb_status_i["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           - sb_status_i['Pac_total_W']  # Entladeleistung SB, positiv beim Entladen, daher -
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
        elif battery_status == (False, False):  # SonnenBatterie idle
            lade_soll_w = (sb_status_i["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
    elif konf['laden_prio'] == 'PV':  # Getestet
        lade_soll_w = (sb_status_i["Production_W"]  # Einspeiseleistung
                       - sb_status_i["Consumption_W"]  # Verbrauch
                       + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                       - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                       )
    elif konf['laden_prio'] == 'PV+':  # Ungetestet
        if sb_status_i['USOC'] > konf['min_batterie_soc']:
            lade_soll_w = (sb_status_i['Production_W']  # PV-Leistung
                           - sb_status_i['Consumption_W']  # Haus-Verbrauch inkl. go-E Ladeleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           + konf['sb_max_w']  # Maximale Entladeleistung SB
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
        else:
            lade_soll_w = (sb_status_i['Production_W']  # PV-Leistung
                           - sb_status_i['Consumption_W']  # Haus-Verbrauch inkl. go-E Ladeleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
    elif konf['laden_prio'] == 'frei':  # Ungetestet
        lade_soll_w = 99999  # Symbolischer Wert

    # Umrechnung Watt → Ampere inkl. aktuelle Leistungsfaktoren, falls es sie gibt
    if 0 not in goe_status_i['nrg'][0:3]:  # Charger an Drehstrom (3~) angeschlossen, Drehstrom-Ampere-berechnen
        lade_soll_amp = lade_soll_w / (3 ** 0.5 * goe_u)
        print(f'Formel A Soll: {lade_soll_amp}', end='')
    else:  # Charger an Wechselstrom (1~) angeschlossen, Wechselstrom-Ampere berechnen.
        lade_soll_amp = lade_soll_w / goe_status_i['nrg'][0]  # Ungetestet

    lade_soll_amp = math.floor(lade_soll_amp)  # Abrunden und in int konvertieren

    if lade_soll_w == 99999:
        lade_soll_amp = 32  # Maximaler Wert, den irgendein go-Echarger kann, wird im Folgenden dann gedeckelt

    lade_soll_amp = min(lade_soll_amp, int(goe_status_i['cbl']))  # Auf Anschlusswert deckeln

    if goe_status_i['loe'] == '1':  # Falls Lastverteilung aktiv. Ungetestet
        lade_soll_amp = min(lade_soll_amp, int(goe_status_i['loa']))  # Auf max. Stromwert aus Lastverteilung deckeln

    lade_soll_amp = max(lade_soll_amp, konf['zoe_modus'] * 6)  # Falls Zoe-Modus aktiv: auf min 6A heben

    # Maximale Veränderungsgeschwindigkeit auf sprung_max_a deckeln, wenn simulieren == False
    if abs(lade_soll_amp - int(goe_status_i['amp'])) > konf['sprung_max_a'] and not konf['simulieren']:
        if lade_soll_amp > int(goe_status_i['amp']):
            lade_soll_amp = int(goe_status_i['amp']) + konf['sprung_max_a']
        elif lade_soll_amp < int(goe_status_i['amp']):
            lade_soll_amp = int(goe_status_i['amp']) - konf['sprung_max_a']
    print(f'  ==>  Sprung A Soll: {lade_soll_amp}', end='')
    # Prüfung anhand vergangener Datenpunkte, ob der neue Ladestrom eine zu hohe Ladeleistung generiert
    while lade_soll_amp in ladekurve and ladekurve[lade_soll_amp] > lade_soll_w:
        lade_soll_amp -= 1
    if lade_soll_amp in ladekurve:
        lade_soll_w = ladekurve[lade_soll_amp]

    print(f'  ==>  Ladekurve A Soll: {lade_soll_amp}')

    return {'A': lade_soll_amp, 'W': lade_soll_w}


def goe_setzen(parameter: str, steuerwert: int, goe_status_i: dict, konf: dict):
    """Steuert den übergebenen Parameter am Go-eCharger auf den gegebenen Wert an und überprüft, ob die Änderung
    angenommen wurde.

    :param parameter: Parameter / Wert-Name, der gesetzt werden soll
    :param steuerwert: Steuerwert, auf den der Parameter gesetzt werden soll
    :param goe_status_i: aktuelles dict-Objekt des Go-eChargers
    :param konf: dict-Objekt mit der aktuellen Konfiguration
    :return: Bool-Wert True falls erfolgreich, False falls nicht erfolgreich
    """
    import requests

    goe_mqtt_url = 'http://' + konf['goe_adresse'] + '/mqtt?payload='  # Nutzt V1 API

    if konf['simulieren']:  # Im Simulationsmodus nichts tun
        return True

    if parameter == 'amx':  # Sonderfall amx wird gesetzt, aber der Return-Wert, der sich ändert, ist amp
        parameter_kontrolle = 'amp'
    else:
        parameter_kontrolle = parameter

    # Muss der Wert überhaupt gesetzt werden?
    if not parameter_kontrolle == 'rst' and not goe_status_i[parameter_kontrolle] == str(steuerwert):
        try:
            goe_return = requests.get(f'{goe_mqtt_url}{parameter}={steuerwert}', timeout=konf['wartezeit'])
        except Exception as connect_err:
            log_event(f'Fehler {connect_err} beim Setzen der Daten am Go-eCharger', konf)
            return False
    else:
        if parameter_kontrolle == 'amp':
            pass  # Wenn Ladeleistung nicht gesetzt werden muss, muss das auch nicht ausgegeben werden
        else:
            log_event(f'Go-E Parameter {parameter_kontrolle} ist bereits {steuerwert} und wurde daher nicht gesetzt.',
                      konf)
        return True

    if goe_return.status_code == 200:  # War das Setzen erfolgreich (schnittstellenseitig)?
        goe_status_i = goe_return.json()
        if str(steuerwert) == goe_status_i[parameter_kontrolle]:  # War das Setzen erfolgreich (wertseitig)?
            return True
        else:
            log_event(f'Fehler beim Setzen von {parameter} am Go-E, {steuerwert} wurde gesetzt aber Wert ist '
                      f'{goe_status_i[parameter_kontrolle]}!', konf)
            return False
    else:
        log_event(f'Go-E MQTT HTTP Fehler Status {goe_return.status_code}', konf)
        return False


def log_nrg(objekt: str, objekt_status: dict, konf: dict):
    """Erstellt bzw. aktualisiert eine Logdatei mit dem heutigen Datum als Dateinamen im relativen Verzeichnis logs.

    :param objekt: Kann "goe" oder "sb" sein. Wird ausschließlich für die Logdatei als Suffix gebrauch
    :param objekt_status: dict-Objekt mit den Daten, die geloggt werden sollen.
    :param konf: dict-Objekt mit der aktuellen Konfiguration
    :return: Bool-Wert True falls erfolgreich, False falls nicht erfolgreich
    """
    import time
    import os

    if konf['logging_nrg']:
        log_name = f'logs\\{time.strftime("%Y-%m-%d")}-{objekt}-log.csv'

        if not os.path.isfile(log_name):
            try:
                with open(log_name, 'x') as log:
                    log_event(f'Erstelle neue Logdatei <{log_name}>', konf)
                    log.write('Uhrzeit_F;')
                    for parameter in objekt_status:
                        log.write(f'{parameter};')
                    log.write('\n')
            except FileExistsError:
                print(f'    Aktualisiere bestehende Logdatei <{log_name}>')
            except FileNotFoundError:  # Der Ordner wurde während der Laufzeit gelöscht
                print('!!!!Der Unterordner <logs> existiert nicht im Arbeitsverzeichnis, bitte erstellen!')
                raise
            except Exception as logfile_err:
                print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
                print(logfile_err)
                raise

        try:
            with open(log_name, 'a') as log:
                log.write(f'{time.strftime("%H:%M:%S")};')
                for wert in objekt_status.values():
                    log.write(f'{wert};')
                log.write('\n')
        except Exception as logwrite_err:
            print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
            print(logwrite_err)
            raise


def log_event(meldung: str, konf: dict):
    """Programm-Meldungen loggen (bekommt einen String, loggt ihn mit Zeitstempel und gibt ihn per print aus)

    :param meldung: Text der Meldung
    :param konf: dict-Objekt mit der aktuellen Konfiguration
    """
    import time
    import os

    print(f'    {meldung}')
    if konf['logging_events']:
        log_name = f'logs\\{time.strftime("%Y-%m-%d")}-sys-log.txt'

        # Aktuelle Konfiguration in Logdatei-Kopf schreiben beim Start, falls nötig Datei erstellen
        if not os.path.isfile(log_name):
            try:
                log = open(log_name, 'x')
                log.write(f'Logdatei {log_name}, erstellt vom SB-GoE-Überschussladen von Musicaloris.\n')
                log.close()
                print(f'    Neue Logdatei <{log_name}> erstellt.')
            except FileExistsError:
                print(f'    Aktualisiere bestehende Logdatei <{log_name}>')
                with open(log_name, 'a') as log:
                    log.write('\n' + ('-' * 35) + '\n')
            except Exception as logfile_err:
                print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
                print(logfile_err)
                raise
            finally:
                with open(log_name, 'a') as log:
                    log.write(f'Programmstart um {time.strftime("%H:%M:%S")}. Aktuelle Konfiguration:\n')
                    for config_wert in konf:
                        log.write(f'{config_wert} = {konf[config_wert]}\n')
                    log.write('\nMeldungen:\n')

        try:
            with open(log_name, 'a') as log:
                log.write(f'{time.strftime("%H:%M:%S")}: {meldung}\n')
        except Exception as logwrite_err:
            print(f'!!!!Fehler beim Arbeiten mit Logdatei <{log_name}>:')
            print(logwrite_err)
            raise


def abwarten(fehler: bool, konf: dict, zyklus_timestamp: float):
    """Warten bis zum nächsten Zyklus

    :param fehler: Wird die Funktion regulär (False) oder aus einem Fehler (True) heraus aufgerufen?
    :param konf: dict-Objekt mit der aktuellen
    :param zyklus_timestamp: Zeitstempel des aktuellen Zyklus'
    """
    import time

    print('-' * 10)
    print('Zum Beenden des Programms Strg + C drücken.')

    if fehler:
        print('Nächster Versuch in ', end='', flush=True)
    else:
        print('Nächstes Update in ', end='', flush=True)

    countdown = konf['wartezeit']
    countdown_zuletzt = int(konf['wartezeit'] - (time.time() - zyklus_timestamp))
    print(f'{countdown_zuletzt}... ', end='', flush=True)
    while time.time() < zyklus_timestamp + konf['wartezeit'] and countdown > 0:
        time.sleep(0.1)
        countdown = int(konf['wartezeit'] - (time.time() - zyklus_timestamp))
        if countdown < countdown_zuletzt:
            print(f'{countdown}... ', end='', flush=True)
            countdown_zuletzt = countdown
    print('\n')


def konsole_leeren():
    """Leert die Konsole auf div. Plattformen. Wird im Projekt aktuell nicht genutzt."""
    import os

    if os.name == 'nt':
        os.system('cls')
    elif os.name == 'posix':
        os.system('clear')
    else:
        print('#' * 35)
