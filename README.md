# SB-GoE-Überschussladen
## Überschussladen mit einer SonnenBatterie und einem Go-eCharger

Ein Python-Skript zum Photovoltaik-Überschussladen von Elektrofahrzeugen. Alle beteiligten Geräte (Skript-Host, SonnenBatterie und Go-eCharger) müssen sich in einem Netzwerk befinden, innerhalb dessen der Skript-Host beide erreichen kann. Es wird keine Cloud-API genutzt, nur lokale Kommunikation.

Entwickelt, um ein Projekt = eine Motivation zum Python-Lernen zu haben - im Wissen, dass es fertige Projekte gibt, die das alles schon mal gelöst haben - siehe zB https://solaranzeige.de/ :)

Momentan läuft es auf Windows, und sollte (mit ggf. minimalen Anpassungen) auch auf Linux (Desktop) laufen. Auf Android läuft es wegen der verwendeten keyboard-Library nicht - diese wird aber nur zum Beenden genutzt, ein keyboard-loser Fork wäre also schnell erstellt (müsste dann zum Beenden gekillt werden oder so).

Langfristig soll es energiesparend auf einem Raspberry o.Ä. laufen. Dafür muss aber die (remote- oder GUI-) Steuerung noch anders werden (und ich muss erstmal einen Raspberry in die Finger bekommen).

Meine Entwicklungs- und Test-Konfiguration:
- Windows 10 / Python 3.11.4
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
