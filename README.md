# SB-GoE-Überschussladen
## Überschussladen mit einer SonnenBatterie und einem Go-eCharger

Ein Python-Skript zum Photovoltaik-Überschussladen von Elektrofahrzeugen. Alle beteiligten Geräte (Skript-Host, SonnenBatterie und Go-eCharger) müssen sich in einem Netzwerk befinden, innerhalb dessen der Skript-Host beide erreichen kann. Es wird keine Cloud-API genutzt, nur lokale Kommunikation.

Entwickelt, um ein Projekt = eine Motivation zum Python-Lernen zu haben - im Wissen, dass es fertige Projekte gibt, die das alles schon mal gelöst haben - siehe z. B. https://solaranzeige.de/ :)

Momentan läuft es auf den u.g. Entwicklungsplattformen.

Meine Entwicklungs- und Test-Konfiguration:
- Windows 10 / Python 3.11.4
- Raspberry Pi4B (4GB RAM) mit PiOS 11 (bullseye) / Python 3.9.2
- SonnenBatterie 10
  - SonnenModule 4
  - Software Version 1.9.4.2021374
  - JSON API v2 Methode "status"
- Go-eCharger Home+ 22kW
  - Hardware Version 2
  - Firmware Version 041 + 042.0
  - API v1
- Renault Zoe R110 Generation 1

Bei abweichenden Konfigurationen können unerwartete Dinge passieren, es werden aber wohl keine Dinge in Flammen aufgehen :)

Für Feedback, Fragen usw. bin ich hier oder per Mail unter sbgoe@musicaloris.de erreichbar.

Genutzte Dokumentation:
- Go-E API Doku: https://github.com/goecharger/go-eCharger-API-v1/blob/master/go-eCharger%20API%20v1%20DE.md
- SonnenBatterie API Doku: https://doc.musicaloris.de/sonnenBatterie_JSON_API_v2_status.pdf
