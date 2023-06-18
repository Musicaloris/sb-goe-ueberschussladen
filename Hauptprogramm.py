"""PV-Überschussladen mit einer SonnenBatterie und einem Go-eCharger.
Programm CC-BY Musicaloris
Projekt-Repository:
Webseite https://www.musicaloris.de/"""

# Python Standard Libraries importieren
import os  # Für das Leerräumen der Konsole und Dateioperationen
import sys  # Für Systemoperationen
import time  # Für das Setzen von Zeitstempeln und Wartefunktionen
import math  # Für das Rechnen
import tomllib  # Für das Einlesen der Konfigurationsdatei

# 3rd Party Libraries importieren
import keyboard  # Für das Abfragen, ob eine Taste gedrückt ist
import requests  # Für das Abrufen der Daten

# Custom Library dieses Projekts importieren
from sbgoelib import *

# Konstanten und Startwerte aus Konfigurationsdatei einlesen
try:
    with open('config.toml', 'rb') as konfiguration_datei:
        konf = tomllib.load(konfiguration_datei)
except tomllib.TOMLDecodeError as toml_err:
    print(f'Fehler beim Einlesen der Konfigurationsdatei <config.toml>. Ist die Datei gemäß TOML-Standard kodiert?')
    print(f'Fehlermeldung: {toml_err}')
    sys.exit(1)

konfigurationswerte_pruefen(konf)  # Prüfen der Konfigurationswerte auf Plausibilität

# URLs setzen
sb_status_url = 'http://' + konf['sb_adresse'] + '/api/v2/status'  # Nutzt v2 JSON API
goe_status_url = 'http://' + konf['goe_adresse'] + '/status'  # Nutzt v1 API
goe_mqtt_url = 'http://' + konf['goe_adresse'] + '/mqtt?payload='  # Nutzt V1 API


def daten_holen(objekt_name: str, objekt: dict, url: str):
    """Holt sich die JSON-Daten von der Hardware über das lokale Netzwerk.

    :param objekt_name: Entweder "Go-E" oder "SB"
    :param objekt: dict-Objekt aus den JSON-Daten und Metainformationen, min. 'zeitstempel' muss initialisiert sein
    :param url: URL, von der die Funktion per GET die JSON-Daten holt. Wird im Programmkopf definiert.
    :return: dict-Objekt aus den aktualisierten JSON-Daten falls erfolgreich, False falls nicht erfolgreich
    """
    if time.time() >= objekt['zeitstempel'] + konf['wartezeit']:
        try:
            print(f'    Hole aktuelle Daten von {objekt_name}...', end='', flush=True)
            antwort = requests.get(url, timeout=konf['wartezeit'])
        except Exception as err:
            log_event(f'{objekt_name} Verbindungsfehler, Details: {err}')
        else:
            if antwort.status_code == 200:
                print('OK')
                return {'objekt': objekt_name, 'status_code': antwort.status_code,
                        'zeitstempel': time.time()} | antwort.json()
            else:
                log_event(f'{objekt_name} HTTP Fehler Status {antwort.status_code}')
                return {'objekt': objekt_name, 'zeitstempel': zyklus_timestamp}
    else:
        return objekt


def goe_ladeleistung_bestimmen(sb_status_i: dict, goe_status_i: dict):
    """Errechnet die aktuell maximal mögliche Ladeleistung anhand der gegebenen Bedingungen.

    :param sb_status_i: dict-Objekt aus den JSON-Daten und Metainformationen der SonnenBatterie
    :param goe_status_i: dict-Objekt aus den JSON-Daten und Metainformationen des Go-eChargers
    :return: dict-Objekt mit der errechneten Leistung in A und W
    """
    global ladekurve
    goe_leistung_w = goe_status_i['nrg'][11] * 10  # Go-E gibt die Leistung in Vielfachen von 10W aus
    lade_soll_w = 0
    goe_u = math.fsum(goe_status_i['nrg'][0:3]) / 3  # Durchschnitt über die Spannungen der drei Einzelphasen

    print(f'Ladeleistung wird bestimmt im Modus {konf["laden_prio"]}: {konf["laden_prio_text"][konf["laden_prio"]]}.\n')

    if konf['laden_prio'] == 'Überschuss':
        if sb_status_i['BatteryCharging']:  # SonnenBatterie lädt, SB-Ladestrom muss beschützt werden
            lade_soll_w = (sb_status["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           + sb_status_i['Pac_total_W']  # Ladeleistung SB, negativ beim Aufladen, daher plus
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
        elif sb_status_i['BatteryDischarging']:  # SonnenBatterie entlädt, in diesem Modus nicht erwünscht!
            lade_soll_w = (sb_status["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           - sb_status_i['Pac_total_W']  # Entladeleistung SB, positiv beim Entladen, daher minus
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
        elif not sb_status_i['BatteryDischarging'] and not sb_status_i['BatteryCharging']:  # SonnenBatterie idle
            lade_soll_w = (sb_status["GridFeedIn_W"]  # Einspeiseleistung
                           + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                           - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                           )
    elif konf['laden_prio'] == 'PV':
        lade_soll_w = (sb_status["Production_W"]  # Einspeiseleistung
                       - sb_status["Consumption_W"]  # Verbrauch
                       + goe_leistung_w  # Ladeleistung go-E addieren, weil sie zur Verfügung steht
                       - konf['ladeleistung_puffer_W']  # Einspeisepuffer
                       )
    elif konf['laden_prio'] == 'PV+':
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
    elif konf['laden_prio'] == "frei":
        lade_soll_w = 99999  # Symbolischer Wert
    else:
        global forrest
        forrest = 'Ungültiger Lademodus'
        log_event(f'Lademodus {konf["laden_prio"]} ist nicht implementiert!')

    # Umrechnung Watt → Ampere inkl. aktuelle Leistungsfaktoren, falls es sie gibt
    if 0 not in goe_status_i['nrg'][0:3]:  # Charger an Drehstrom (3~) angeschlossen, Drehstrom-Ampere-berechnen
        lade_soll_amp = lade_soll_w / (3 ** 0.5 * goe_u)
        print(f'Formel A Soll: {lade_soll_amp}', end='')
    else:  # Charger an Wechselstrom (1~) angeschlossen, Wechselstrom-Ampere berechnen
        lade_soll_amp = lade_soll_w / goe_status_i['nrg'][0]

    lade_soll_amp = math.floor(lade_soll_amp)  # Abrunden und in int konvertieren

    if lade_soll_w == 99999:
        lade_soll_amp = 32  # Maximaler Wert, den irgendein go-Echarger kann, wird im Folgenden dann gedeckelt

    lade_soll_amp = min(lade_soll_amp, int(goe_status_i['cbl']))  # Auf Anschlusswert deckeln

    if goe_status_i['loe'] == "1":  # Falls Lastverteilung aktiv
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

    return {"A": lade_soll_amp, "W": lade_soll_w}


def goe_setzen(parameter: str, steuerwert: int, goe_status_i: dict):
    """Steuert den übergebenen Parameter am Go-eCharger auf den gegebenen Wert an und überprüft, ob die Änderung
    angenommen wurde.

    :param parameter: Parameter / Wert-Name, der gesetzt werden soll
    :param steuerwert: Steuerwert, auf den der Parameter gesetzt werden soll
    :param goe_status_i: aktuelles dict-Objekt des Go-eChargers
    :return: Bool-Wert True falls erfolgreich, False falls nicht erfolgreich
    """
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
        except Exception as err:
            log_event(f'Fehler {err} beim Setzen der Daten am Go-eCharger')
            return False
    else:
        if parameter_kontrolle == 'amp':
            pass  # Wenn Ladeleistung nicht gesetzt werden muss, muss das auch nicht ausgegeben werden
        else:
            log_event(f'Go-E Parameter {parameter_kontrolle} ist bereits {steuerwert} und wurde daher nicht gesetzt.')
        return True

    if goe_return.status_code == 200:  # War das Setzen erfolgreich (schnittstellenseitig)?
        goe_status_i = goe_return.json()
        if str(steuerwert) == goe_status_i[parameter_kontrolle]:  # War das Setzen erfolgreich (wertseitig)?
            return True
        else:
            log_event(f'Fehler beim Setzen von {parameter} am Go-E, {steuerwert} wurde gesetzt aber Wert ist '
                      f'{goe_status_i[parameter_kontrolle]}!')
            return False
    else:
        log_event(f'Go-E MQTT HTTP Fehler Status {goe_return.status_code}')
        return False


def log_nrg(objekt: str, objekt_status: dict):
    """Erstellt bzw. aktualisiert eine Logdatei mit dem heutigen Datum als Dateinamen im relativen Verzeichnis logs.

    :param objekt: Kann "goe" oder "sb" sein. Wird ausschließlich für die Logdatei als Suffix gebrauch
    :param objekt_status: dict-Objekt mit den Daten, die geloggt werden sollen.
    :return: Bool-Wert True falls erfolgreich, False falls nicht erfolgreich
    """
    if konf['logging_nrg']:
        log_name = f'logs\\{time.strftime("%Y-%m-%d")}-{objekt}-log.csv'
        global firstrun
        if firstrun <= 2:
            try:
                os.mkdir('logs')
                print('Verzeichnis <logs> wurde erstellt.')
            except FileExistsError:
                pass
            except Exception as err:
                print('!!!!Fehler beim Erstellen des Verzeichnisses <logs>:')
                print(err)
                raise
            firstrun += 1

        if not os.path.isfile(log_name):
            try:
                with open(log_name, 'x') as log:
                    log_event(f'Erstelle neue Logdatei <{log_name}>')
                    log.write('Uhrzeit_F;')
                    for parameter in objekt_status:
                        log.write(f'{parameter};')
                    log.write('\n')
            except FileExistsError:
                print(f'    Aktualisiere bestehende Logdatei <{log_name}>')
            except FileNotFoundError:
                print('!!!!Der Unterordner <logs> existiert nicht im Arbeitsverzeichnis, bitte erstellen!')
                raise
            except Exception as err:
                print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
                print(err)
                raise

        try:
            with open(log_name, 'a') as log:
                log.write(f'{time.strftime("%H:%M:%S")};')
                for wert in objekt_status.values():
                    log.write(f'{wert};')
                log.write('\n')
        except Exception as err:
            print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
            print(err)
            raise


def log_event(meldung: str):
    """Programm-Meldungen loggen (bekommt einen String, loggt ihn mit Zeitstempel und gibt ihn per print aus)

    :param meldung: Text der Meldung
    """

    print(f'    {meldung}')
    if konf['logging_events']:
        log_name = f'logs\\{time.strftime("%Y-%m-%d")}-sys-log.txt'

        # Aktuelle Konfiguration in Logdatei-Kopf schreiben beim Start, falls nötig Datei erstellen
        global firstrun
        if firstrun and isinstance(firstrun, bool):
            try:
                os.mkdir('logs')
                print('Verzeichnis <logs> wurde erstellt.')
            except FileExistsError:
                pass
            except Exception as err:
                print('!!!!Fehler beim Erstellen des Verzeichnisses <logs>:')
                print(err)
                raise
            firstrun = 1

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
            except Exception as err:
                print(f'!!!!Fehler beim Arbeiten mit <{log_name}>:')
                print(err)
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
        except Exception as err:
            print(f'!!!!Fehler beim Arbeiten mit Logdatei <{log_name}>:')
            print(err)
            raise


def hotkey():
    """Setzt die Variable zum Beenden der Hauptschleife"""
    global forrest
    forrest = 'Exit-Hotkey wurde gedrückt'


def abwarten(fehler: bool):
    """Warten bis zum nächsten Zyklus

    :param fehler: Wird die Funktion regulär (False) oder aus einem Fehler (True) heraus aufgerufen?"""

    print('-' * 10)
    print('Zum Beenden des Programms Strg + Ä drücken.')

    if fehler:
        print('Nächster Versuch in ', end='', flush=True)
    else:
        print('Nächstes Update in ', end='', flush=True)

    countdown = konf['wartezeit']
    countdown_zuletzt = int(konf['wartezeit'] - (time.time() - zyklus_timestamp))
    print(f'{countdown_zuletzt}... ', end='', flush=True)
    while time.time() < zyklus_timestamp + konf['wartezeit'] and forrest == 'run' and countdown > 0:
        time.sleep(0.1)
        countdown = int(konf['wartezeit'] - (time.time() - zyklus_timestamp))
        if countdown < countdown_zuletzt:
            print(f'{countdown}... ', end='', flush=True)
            countdown_zuletzt = countdown
    print('\n')


def konsole_leeren():
    """Leert die Konsole auf div. Plattformen"""
    if os.name == 'nt':
        os.system('cls')
    elif os.name == 'posix':
        os.system('clear')
    else:
        print('#' * 35)


#########################################
# Initialisieren Werte vor der Hauptschleife
firstrun = True
zyklus_timestamp = time.time() - konf['wartezeit']
sb_status = {'objekt': 'SB', 'zeitstempel': zyklus_timestamp}
goe_status = {'objekt': 'Go-E', 'zeitstempel': zyklus_timestamp}
forrest = "run"
goe_err = {'1': 'RCCB (Fehlerstromschutzschalter)',
           '3': 'PHASE (Phasenstörung)',
           '8': 'NO_GROUND (Erdungserkennung)',
           '10': 'INTERNAL (sonstiges)',
           'default': 'INTERNAL (sonstiges / default)'}
goe_stop_laden = False
ladeleistung = {'W': 'undefiniert'}
keyboard.add_hotkey('ctrl+ä', hotkey)
ladekurve = {0: 0}
for datenpunkt_a, datenpunkt_w in konf['ladekurve'].items():  # Zahlenfeld mit Ampere-Watt Beziehungen initialisieren
    ladekurve[int(datenpunkt_a)] = datenpunkt_w

# Programmkopf Konfigurationswerte ausgeben
print('-' * 35)
print('Programm-Konfiguration:')
print(f'    Logging der Energiewerte ist {"de" * (not konf["logging_nrg"])}aktiviert.')
print(f'    Logging der Meldungen ist {"de" * (not konf["logging_events"])}aktiviert.')
print(f'    Go-eCharger Status URL: <{goe_status_url}>')
print(f'    SonnenBatterie Status URL: <{sb_status_url}>')
print(f'    Lademodus <{konf["laden_prio"]}>: {konf["laden_prio_text"][konf["laden_prio"]]}')
if konf['laden_prio'] == 'PV+SB':
    print(f'    Zu erhaltender minimaler Batteriestand: {konf["min_batterie_soc"]}%')
print(f'    Aktualisierungsgeschwindigkeit / Wartezeit: {konf["wartezeit"]} Sekunden')
if konf['simulieren']:
    print('    Simulieren ist aktiv, es werden keine Werte auf den Go-eCharger geschrieben!')
if konf['zoe_modus']:
    print('    Zoe-Modus ist aktiv, statt einer Unterbrechung des Ladevorgangs wird bei zu wenig Leistung der ')
    print('    Ladestrom auf 6A gehalten, damit das Auto nicht einschläft!')
print()
print('-' * 10)

#########################################
while forrest == "run":  # Programm-Hauptschleife
    # Daten aktualisieren zum Schleifenbeginn
    goe_status_puffer = daten_holen("Go-E", goe_status, goe_status_url)
    sb_status_puffer = daten_holen("SB", sb_status, sb_status_url)

    # Konnten die Daten erfolgreich abgeholt werden?
    if 'status_code' in goe_status and 'status_code' in sb_status:  # Daten holen war iO, ab in die Status-Objekte damit
        goe_status = goe_status_puffer
        sb_status = sb_status_puffer
    else:  # Daten sind invalide, vermutlich Fehler beim Holen
        zyklus_timestamp = time.time()
        abwarten(True)
        continue

    ladekurve[int(goe_status['amp'])] = goe_status["nrg"][11] * 10  # ladekurve mit aktuellem Datenpunkt updaten
    ladeleistung = goe_ladeleistung_bestimmen(sb_status, goe_status)  # Ladeleistung bestimmen

    # Es gibt Daten von Go-E und SB, aktuelle Daten ausgeben
    print(f'\nAktuelle Werte Stand {time.strftime("%H:%M:%S")}:')
    print(f'    {str(sb_status["Production_W"]).rjust(5)} W PV-Leistung')
    print(f'    {str(sb_status["Consumption_W"]).rjust(5)} W Verbrauch '
          f'{"inkl. Go-E" * bool(int(goe_status["nrg"][11]))}')
    if int(goe_status["nrg"][11]):  # Falls Go-E Ladeleistung > 0
        print(f'    {str(goe_status["nrg"][11] * 10).rjust(5)} W Go-E Ladeleistung')
        print(f'    {str(sb_status["Consumption_W"] - int(goe_status["nrg"][11]) * 10).rjust(5)} W '
              f'Verbrauch exkl. Go-E')
    if ladeleistung['W'] > 0:
        print(f'    {str(ladeleistung["W"]).rjust(5)} W errechnete mögliche Go-E Ladeleistung')
    if sb_status['Pac_total_W'] > 0 and sb_status['BatteryDischarging']:
        print(f'    {str(abs(sb_status["Pac_total_W"])).rjust(5)} W SonnenBatterie-Entladeleistung bei '
              f'{sb_status["USOC"]}% Batterie-Ladestand')
    elif sb_status['Pac_total_W'] < 0 and sb_status['BatteryCharging']:
        print(f'    {str(abs(sb_status["Pac_total_W"])).rjust(5)} W SonnenBatterie-Aufladeleistung bei '
              f'{sb_status["USOC"]}% Batterie-Ladestand')
    if sb_status['GridFeedIn_W'] < 0:
        print(f'    {str(abs(sb_status["GridFeedIn_W"])).rjust(5)} W Netzbezug')
    else:
        print(f'    {str(abs(sb_status["GridFeedIn_W"])).rjust(5)} W Einspeiseleistung')
    if not sb_status['BatteryDischarging'] and not sb_status['BatteryCharging']:
        print(f'    {str(sb_status["USOC"]).rjust(5)} % Ladestand SonnenBatterie im idle')
    print('-' * 10)
    print('Meldungen:')

    # Liegt ein Fehler am go-E an? Automatischer Reset-Versuch.
    if not goe_status['err'] == "0":
        log_event(f'Am go-eCharger liegt ein Fehler an: Code {goe_status["err"]} {goe_err[goe_status["err"]]}')
        log_event('Versuche automatischen Reset / Reboot über MQTT.')
        try:
            requests.get(f'{goe_mqtt_url}rst=1', timeout=konf['wartezeit'])
            print('Bitte 10s warten...')
            time.sleep(10)
            goe_rst = daten_holen('Go-E', goe_status, goe_status_url)
        except Exception as rst_err:
            log_event(f'Fehler {rst_err} beim Senden des Resets am Go-eCharger')
            goe_rst = False
            forrest = 'Go-E Fehler lässt sich nicht resetten'
        else:
            if goe_rst.status_code == 200:
                goe_rst = bool(int(goe_rst.json()["rbc"]) > int(goe_status["rbc"]))
            else:
                log_event(f'Go-E MQTT HTTP Fehler Status {goe_rst.status_code}')
        log_event(f'Automatischer Reset / Reboot war {"nicht " * goe_rst}erfolgreich.')
        if not goe_rst:
            forrest = 'Go-E Fehler lässt sich nicht resetten'
        zyklus_timestamp = time.time()
        abwarten(True)
        if not konf['simulieren']:
            continue

    # ist ein Auto angeschlossen und bereit?
    if goe_status['car'] == "1":
        log_event('Kein Fahrzeug am Go-eCharger angeschlossen.')
    elif goe_status['car'] == "2":
        if goe_status["nrg"][11] * 10 == 0:
            log_event('Fahrzeug ist am Go-eCharger angeschlossen und bereit zum Laden.')
        else:
            log_event('Fahrzeug ist am Go-eCharger angeschlossen und lädt.')
    elif goe_status['car'] == "3":
        log_event('Go-eCharger wartet auf Fahrzeug.')
        zyklus_timestamp = time.time()
        abwarten(False)
    elif goe_status['car'] == "4":
        log_event('Go-eCharger meldet Ladung beendet (manuell, durch Go-E oder durch Auto), Auto angeschlossen.')
        # Default-Ladekurve laden, da beim Beenden Ladeleistung und Strom entkoppelt sind
        for datenpunkt_a, datenpunkt_w in konf['ladekurve'].items():
            ladekurve[str(datenpunkt_a)] = datenpunkt_w

    # Befindet sich der Go-E im Stop-Modus (wurde eine maximale Lademenge definiert)?
    if goe_status['stp'] == "2":
        goe_stop_laden = True
        log_event(f'Automatische Abschaltung nach {goe_status["dwo"] / 10} kWh ist aktiviert.')
        log_event(f'Davon sind bereits {int(goe_status["dws"]) / 3600000} kWh geladen.')
    elif goe_status['stp'] == "0" and goe_stop_laden:
        log_event('Das Laden am Go-eCharger wurde durch die automatische Abschaltung beendet, oder die Ladegrenze wurde'
                  ' manuell entfernt.')
        laden_fortsetzen = input('Soll weiter geladen werden? (J/N) >> ')
        if laden_fortsetzen.lower() == 'j':
            goe_stop_laden = False
            log_event('(J) OK, es wird weiter geladen.')
        else:
            log_event('Dieses Programm wird beendet, um das Laden nicht automatisch wieder zu starten.')
            forrest = 'Laden wurde durch die automatische Abschaltung beendet'  # Damit wird die Hauptschleife beendet
        continue

    # Yaey, Verbindung steht, Auto bereit! Aber ist genug Ladeleistung da? Der Go-E Charger lädt mit mindestens 6A!
    if ladeleistung['A'] < 6:
        log_event(f'Nicht ausreichend Überschuss zum Fahrzeug laden: Möglicher Ladestrom: {ladeleistung["A"]} A, '
                  f'minimaler go-e Ladestrom 6 A')
        if goe_status['alw'] == '1':
            if goe_setzen('alw', 0, goe_status):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Laden wurde aufgrund zu kleiner zur Verfügung '
                          f'stehender Leistung unterbrochen.')
            else:
                log_event('Fehler beim Unterbrechen der Fahrzeugladung!')
    elif ladeleistung['A'] >= 6:  # Yaey, es ist genug Ladeleistung da! Ladeleistung setzen!
        if goe_status['alw'] == "1":  # Wenn Laden schon erlaubt ist, Ladeleistung setzen
            if goe_setzen('amx', ladeleistung['A'], goe_status):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Ladestrom-Vorgabe ist {ladeleistung["A"]} A' +
                          f' (war {goe_status["amp"]} A)' * (not int(goe_status["amp"]) == ladeleistung["A"]) +
                          '.'
                          )
            else:
                log_event('Fehler beim Setzen der Ladeleistung!')
        else:  # Wenn Laden noch nicht erlaubt war, Ladeleistung setzen und Laden erlauben
            if goe_setzen('amx', ladeleistung['A'], goe_status) and goe_setzen('alw', 1, goe_status):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Ladevorgang wurde mit {ladeleistung["A"]} A gestartet '
                          f'/ wieder aufgenommen!')
            else:
                log_event('Ladevorgang konnte nicht gestartet / wieder aufgenommen werden.')
        if ladeleistung['A'] == 6 and konf['zoe_modus']:
            log_event('Hinweis: Der Zoe-Modus ist aktiv!')

    if konf['logging_nrg']:  # Es ist wichtig, dass immer zuerst der goe-log und dann der sb-log geschrieben wird!
        log_nrg("goe", goe_status)
        log_nrg("sb", sb_status)

    zyklus_timestamp = time.time()  # Zeitstempel erneuern
    abwarten(False)

    konsole_leeren()
    # Ende der Hauptschleife

else:  # Block für das reguläre Beenden der Hauptschleife, else gehört noch zu while
    print('-' * 35)
    log_event(f'Das Programm wurde regulär beendet. Grund: {forrest}')
# Ende der Hauptschleife


# Reste zusammenfegen
if forrest == 'run':
    print('-' * 35)
    log_event(f'Das Programm wurde unerwartet beendet.')

keyboard.remove_all_hotkeys()
# Programm-Ende
