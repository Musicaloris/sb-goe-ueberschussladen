"""PV-Überschussladen mit einer SonnenBatterie und einem Go-eCharger.
Programm CC-BY Musicaloris
Projekt-Repository: https://github.com/Musicaloris/sb-goe-ueberschussladen/
Webseite Musicaloris: https://www.musicaloris.de/"""

# Python Standard Libraries importieren
import os  # Für das Leerräumen der Konsole und Dateioperationen
import sys  # Für Systemoperationen
import time  # Für das Setzen von Zeitstempeln und Wartefunktionen
import tomllib  # Für das Einlesen der Konfigurationsdatei

# 3rd Party Libraries importieren
import keyboard  # Für das Abfragen, ob eine Taste gedrückt ist
import requests  # Für das Abrufen der Daten

# Funktionen-Library dieses Projekts importieren
from sbgoelib import *


# Konfigurationsdatei einlesen
try:
    with open('config.toml', 'rb') as konfiguration_datei:
        konf = tomllib.load(konfiguration_datei)
except tomllib.TOMLDecodeError as toml_err:
    print(f'Fehler beim Einlesen der Konfigurationsdatei <config.toml>. Ist die Datei gemäß TOML-Standard kodiert?')
    print(f'Fehlermeldung: {toml_err}')
    sys.exit(1)

# Prüfen der Konfigurationswerte auf Plausibilität
konfigurationswerte_pruefen(konf)


def hotkey():
    """Setzt die Variable zum Beenden der Hauptschleife"""
    global forrest
    forrest = 'Exit-Hotkey wurde gedrückt'


# Initialisieren Variablen
sb_status_url = 'http://' + konf['sb_adresse'] + '/api/v2/status'  # Nutzt v2 JSON API
goe_status_url = 'http://' + konf['goe_adresse'] + '/status'  # Nutzt v1 API
goe_mqtt_url = 'http://' + konf['goe_adresse'] + '/mqtt?payload='  # Nutzt V1 API
zyklus_timestamp = time.time() - konf['wartezeit']  # Zeitstempel in der Vergangenheit initialisieren
sb_status = {'objekt': 'SB', 'zeitstempel': zyklus_timestamp}  # Standard-Objektzustand
goe_status = {'objekt': 'Go-E', 'zeitstempel': zyklus_timestamp}  # Standard-Objektzustand
forrest = "run"  # Variable zur Kontrolle der Hauptschleife
goe_stop_laden = False
ladeleistung = {'W': 'undefiniert'}  # Standard-Objektzustand
keyboard.add_hotkey('ctrl+ä', hotkey)  # Hotkey zum regulären Beenden der Hauptschleife aktivieren
ladekurve = {0: 0}  # Standard-Objektzustand

# Ladekurve aus Konfigurationsdatei laden
for datenpunkt_a, datenpunkt_w in konf['ladekurve'].items():  # Zahlenfeld mit Ampere-Watt Beziehungen initialisieren
    ladekurve[int(datenpunkt_a)] = datenpunkt_w

# Initialisieren der Logdatei-Verzeichnisse falls Logging aktiviert
if konf['logging_nrg'] or konf['logging_events']:
    try:
        os.mkdir('logs')
        print('Verzeichnis <logs> wurde erstellt.')
    except FileExistsError:
        pass
    except Exception as err:
        print('!!!!Fehler beim Erstellen des Verzeichnisses <logs>:')
        print(err)
        raise

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
while forrest == "run":  # Programm-Hauptschleife. Ist wie eine Schachtel Pralinen.
    # Daten aktualisieren zum Schleifenbeginn
    goe_status_puffer = daten_holen("Go-E", goe_status, goe_status_url, konf)
    sb_status_puffer = daten_holen("SB", sb_status, sb_status_url, konf)

    # Konnten die Daten erfolgreich abgeholt werden?
    if 'status_code' in goe_status and 'status_code' in sb_status:  # Daten holen war iO, ab in die Status-Objekte damit
        goe_status = goe_status_puffer
        sb_status = sb_status_puffer
    else:  # Daten sind invalide, vermutlich Fehler beim Holen
        zyklus_timestamp = time.time()
        abwarten(True, konf, zyklus_timestamp)
        continue

    ladekurve[int(goe_status['amp'])] = goe_status["nrg"][11] * 10  # ladekurve mit aktuellem Datenpunkt updaten
    ladeleistung = goe_ladeleistung_bestimmen(sb_status, goe_status, ladekurve, konf)  # Ladeleistung bestimmen

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
        log_event(f'Am go-eCharger liegt ein Fehler an: {konf["goe_err"][goe_status["err"]]}', konf)
        log_event('Versuche automatischen Reset / Reboot über MQTT.', konf)
        try:
            requests.get(f'{goe_mqtt_url}rst=1', timeout=konf['wartezeit'])
            print('Bitte 10s warten...')
            time.sleep(10)
            goe_rst = daten_holen('Go-E', goe_status, goe_status_url, konf)
        except Exception as rst_err:
            log_event(f'Fehler {rst_err} beim Senden des Resets am Go-eCharger', konf)
            goe_rst = False
            forrest = 'Go-E Fehler lässt sich nicht resetten'
        else:
            if goe_rst.status_code == 200:
                goe_rst = bool(int(goe_rst.json()["rbc"]) > int(goe_status["rbc"]))
            else:
                log_event(f'Go-E MQTT HTTP Fehler Status {goe_rst.status_code}', konf)
        log_event(f'Automatischer Reset / Reboot war {"nicht " * goe_rst}erfolgreich.', konf)
        if not goe_rst:
            forrest = 'Go-E Fehler lässt sich nicht resetten'
        zyklus_timestamp = time.time()
        abwarten(True, konf, zyklus_timestamp)
        if not konf['simulieren']:
            continue

    # ist ein Auto angeschlossen und bereit?
    if goe_status['car'] == "1":
        log_event('Kein Fahrzeug am Go-eCharger angeschlossen.', konf)
    elif goe_status['car'] == "2":
        if goe_status["nrg"][11] * 10 == 0:
            log_event('Fahrzeug ist am Go-eCharger angeschlossen und bereit zum Laden.', konf)
        else:
            log_event('Fahrzeug ist am Go-eCharger angeschlossen und lädt.', konf)
    elif goe_status['car'] == "3":
        log_event('Go-eCharger wartet auf Fahrzeug.', konf)
        zyklus_timestamp = time.time()
        abwarten(False, konf, zyklus_timestamp)
    elif goe_status['car'] == "4":
        log_event('Go-eCharger meldet Ladung beendet (manuell, durch Go-E oder durch Auto), Auto angeschlossen.', konf)
        # Default-Ladekurve laden, da beim Beenden Ladeleistung und Strom entkoppelt sind
        for datenpunkt_a, datenpunkt_w in konf['ladekurve'].items():
            ladekurve[str(datenpunkt_a)] = datenpunkt_w

    # Befindet sich der Go-E im Stop-Modus (wurde eine maximale Lademenge definiert)?
    if goe_status['stp'] == "2":
        goe_stop_laden = True
        log_event(f'Automatische Abschaltung nach {goe_status["dwo"] / 10} kWh ist aktiviert.', konf)
        log_event(f'Davon sind bereits {int(goe_status["dws"]) / 3600000} kWh geladen.', konf)
    elif goe_status['stp'] == "0" and goe_stop_laden:
        log_event('Das Laden am Go-eCharger wurde durch die automatische Abschaltung beendet, oder die Ladegrenze wurde'
                  ' manuell entfernt.', konf)
        laden_fortsetzen = input('Soll weiter geladen werden? (J/N) >> ')
        if laden_fortsetzen.lower() == 'j':
            goe_stop_laden = False
            log_event('(J) OK, es wird weiter geladen.', konf)
        else:
            log_event('Dieses Programm wird beendet, um das Laden nicht automatisch wieder zu starten.', konf)
            forrest = 'Laden wurde durch die automatische Abschaltung beendet'  # Damit wird die Hauptschleife beendet
        continue

    # Yaey, Verbindung steht, Auto bereit! Aber ist genug Ladeleistung da? Der Go-E Charger lädt mit mindestens 6A!
    if ladeleistung['A'] < 6:
        log_event(f'Nicht ausreichend Überschuss zum Fahrzeug laden: Möglicher Ladestrom: {ladeleistung["A"]} A, '
                  f'minimaler go-e Ladestrom 6 A', konf)
        if goe_status['alw'] == '1':
            if goe_setzen('alw', 0, goe_status, konf):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Laden wurde aufgrund zu kleiner zur Verfügung '
                          f'stehender Leistung unterbrochen.', konf)
            else:
                log_event('Fehler beim Unterbrechen der Fahrzeugladung!', konf)
    elif ladeleistung['A'] >= 6:  # Yaey, es ist genug Ladeleistung da! Ladeleistung setzen!
        if goe_status['alw'] == "1":  # Wenn Laden schon erlaubt ist, Ladeleistung setzen
            if goe_setzen('amx', ladeleistung['A'], goe_status, konf):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Ladestrom-Vorgabe ist {ladeleistung["A"]} A' +
                          f' (war {goe_status["amp"]} A)' * (not int(goe_status["amp"]) == ladeleistung["A"]) +
                          '.', konf)
            else:
                log_event('Fehler beim Setzen der Ladeleistung!', konf)
        else:  # Wenn Laden noch nicht erlaubt war, Ladeleistung setzen und Laden erlauben
            if goe_setzen('amx', ladeleistung['A'], goe_status, konf) and goe_setzen('alw', 1, goe_status, konf):
                log_event(f'{"[simuliert] " * konf["simulieren"]}Ladevorgang wurde mit {ladeleistung["A"]} A gestartet '
                          f'/ wieder aufgenommen!', konf)
            else:
                log_event('Ladevorgang konnte nicht gestartet / wieder aufgenommen werden.', konf)
        if ladeleistung['A'] == 6 and konf['zoe_modus']:
            log_event('Hinweis: Der Zoe-Modus ist aktiv!', konf)

    if konf['logging_nrg']:
        log_nrg("goe", goe_status, konf)
        log_nrg("sb", sb_status, konf)

    zyklus_timestamp = time.time()  # Zeitstempel erneuern
    abwarten(False, konf, zyklus_timestamp)

    print('\n' * 2)
    # Ende des Hauptschleife-while-Loop-Codeblocks

else:  # Block für das reguläre Beenden der Hauptschleife, else gehört noch zu while
    print('-' * 35)
    log_event(f'Das Programm wurde regulär beendet. Grund: {forrest}', konf)
###################################


# Reste zusammenfegen
if forrest == 'run':
    print('-' * 35)
    log_event(f'Das Programm wurde unerwartet beendet.', konf)

keyboard.remove_all_hotkeys()  # Alle Hotkeys deaktivieren
